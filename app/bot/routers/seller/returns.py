from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from app.bot.keyboards.inline import catalog_kb, warehouse_return_kb
from app.bot.states.states import ReturnFlow
from app.models.user import User
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.enums import OrderStatus
from app.services import (
    OrderService, 
    ProductService, 
    TransactionService, 
    NotificationService
)
from app.bot.routers.seller.common import MENU_TEXTS
from typing import Any
router = Router(name="seller.returns")


@router.message(F.text.in_({"↩️ Сделать возврат", "↩️ Бозгашти мол"}))
async def start_return(
    message: Message, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    await state.clear()
    order_svc = OrderService(session)
    items = await order_svc.get_store_inventory(user.store_id, include_empty=False)
    if not items:
        await message.answer(_("return_no_products"))
        return
        
    products = [inv.product for inv in items if inv.quantity > 0]
    if not products:
        await message.answer(_("return_no_available"))
        return
    
    await message.answer(
        _("return_title"),
        parse_mode="HTML",
        reply_markup=catalog_kb(
            products, 
            page=0, 
            callback_prefix="return:page", 
            item_callback_prefix="return:select",
            _=_
        )
    )
    await state.set_state(ReturnFlow.select_product)


@router.message(ReturnFlow.select_product, F.text)
async def return_search_product(
    message: Message, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    if message.text.strip() in MENU_TEXTS:
        await state.clear()
        return

    prod_svc = ProductService(session)
    product, matches, inv = await prod_svc.search_store_inventory(
        message.text, user.store_id, require_stock=True
    )

    if product:
        await state.update_data(product_id=product.id)
        await message.answer(
            _("return_selected", sku=product.sku, qty=inv.quantity),
            parse_mode="HTML"
        )
        await state.set_state(ReturnFlow.enter_quantity)
        return
    elif matches:
        await message.answer(
            _("return_search_found"),
            reply_markup=catalog_kb(
                matches,
                page=0,
                callback_prefix="return:page",
                item_callback_prefix="return:select",
                _=_
            )
        )
        return
    else:
        await message.answer(_("return_not_found"))
        return


@router.callback_query(ReturnFlow.select_product, F.data.startswith("return:page:"))
async def return_page_nav(
    callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    page = int(callback.data.split(":")[-1])
    
    result = await session.execute(
        select(Inventory)
        .options(selectinload(Inventory.product))
        .where(
            Inventory.store_id == user.store_id,
            Inventory.quantity > 0
        )
    )
    items = result.scalars().all()
    products = [inv.product for inv in items] if items else []
    
    await callback.message.edit_reply_markup(
        reply_markup=catalog_kb(
            products, 
            page=page, 
            callback_prefix="return:page",
            item_callback_prefix="return:select",
            _=_
        )
    )
    await callback.answer()


@router.callback_query(ReturnFlow.select_product, F.data.startswith("return:select:"))
async def return_select_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, _: Any
) -> None:
    product_id = int(callback.data.split(":")[-1])
    
    result = await session.execute(
        select(Inventory).where(
            Inventory.store_id == user.store_id, 
            Inventory.product_id == product_id
        )
    )
    inv = result.scalar_one_or_none()
    qty = inv.quantity if inv else 0
    
    await state.update_data(product_id=product_id)
    await callback.message.edit_text(_("return_enter_qty", qty=qty))
    await state.set_state(ReturnFlow.enter_quantity)
    await callback.answer()


@router.message(ReturnFlow.enter_quantity)
async def return_enter_quantity(
    message: Message, state: FSMContext, user: User, session: AsyncSession, _: Any
) -> None:
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer(_("sale_invalid_qty"))
        return

    quantity = int(message.text)
    data = await state.get_data()
    product_id = data.get("product_id")
    
    if not product_id:
        await message.answer(_("sale_select_first"))
        await state.clear()
        return

    try:
        product = await session.get(Product, product_id)
        if not product:
             await message.answer(_("sale_not_found"))
             return

        # 1. Determine if this should be a display return
        display_qty_result = await session.execute(
            select(func.coalesce(func.sum(Order.quantity), 0)).where(
                Order.store_id == user.store_id,
                Order.product_id == product_id,
                Order.status == OrderStatus.DISPLAY_DELIVERED,
            )
        )
        display_qty_available = display_qty_result.scalar() or 0
        is_display = display_qty_available >= quantity

        return_type_label = "ВОЗВРАТ ОБРАЗЦОВ" if is_display else "ВОЗВРАТ"

        # 2. Создаем заказ с правильным статусом и фиксируем цену
        return_order = Order(
            store_id=user.store_id,
            product_id=product_id,
            quantity=quantity,
            price_per_item=product.price,
            total_price=product.price * quantity,
            status=OrderStatus.DISPLAY_RETURN_PENDING if is_display else OrderStatus.RETURN_PENDING,
        )

        session.add(return_order)
        await session.flush()
        
        # 3. Передаем в транзакцию возврата
        txn_svc = TransactionService(session)
        await txn_svc.initiate_return(
            store_id=user.store_id,
            user_id=user.id,
            product_id=product_id,
            quantity=quantity,
            order_id=return_order.id,
        )
        
        # COMMIT BEFORE NOTIFICATION to ensure database consistency
        await session.commit()
        
        # 4. Отправляем уведомление на склад
        debt_note = "" if is_display else (
            _("return_notif_wh_instr")
        )
        
        notif_svc = NotificationService(message.bot, session)
        await notif_svc.notify_warehouse(
            text=lambda _t: _t(
                "return_notif_wh",
                type=_t("return_type_samples") if is_display else _t("return_type_goods"),
                store=user.store.name if user.store and user.store.name else _t("store_label"),
                id=return_order.id,
                sku=product.sku,
                qty=quantity,
                note="" if is_display else _t("return_notif_wh_instr")
            ),
            reply_markup=lambda _t: warehouse_return_kb(return_order.id, _=_t)
        )
        
        if is_display:
            seller_msg = _("return_confirm_msg_samples")
        else:
            seller_msg = _("return_confirm_msg_goods")
        await message.answer(seller_msg)

    except ValueError as e:
        await message.answer(_("sale_error", error=str(e)))
    except Exception as e:
        await message.answer(_("sale_system_error"))
        print(f"Error in return_enter_quantity: {e}")
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("order:return:"))
async def quick_return_order(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        # 1. Get the original delivered order
        original_order = await session.get(
            Order, 
            order_id, 
            options=[selectinload(Order.product)]
        )
        if not original_order:
            await callback.answer(_("order_not_found"), show_alert=True)
            return

        product_id = original_order.product_id
        quantity = original_order.quantity

        # 2. Check if the store actually has this quantity available
        inv_stmt = select(Inventory).where(
            Inventory.store_id == user.store_id,
            Inventory.product_id == product_id
        )
        inv_result = await session.execute(inv_stmt)
        inv = inv_result.scalar_one_or_none()
        
        if not inv or inv.quantity < quantity:
            await callback.answer(
                _("return_quick_not_enough"), 
                show_alert=True
            )
            return

        # 3. Determine if this should be a display return
        is_display = (original_order.status == OrderStatus.DISPLAY_DELIVERED)

        # 4. Create a new return order
        return_order = Order(
            store_id=user.store_id,
            product_id=product_id,
            quantity=quantity,
            price_per_item=original_order.product.price,
            total_price=original_order.product.price * quantity,
            status=OrderStatus.DISPLAY_RETURN_PENDING if is_display else OrderStatus.RETURN_PENDING,
        )
        session.add(return_order)
        await session.flush()

        # 5. Initiate the return transaction
        txn_svc = TransactionService(session)
        await txn_svc.initiate_return(
            store_id=user.store_id,
            user_id=user.id,
            product_id=product_id,
            quantity=quantity,
            order_id=return_order.id,
        )
        
        # COMMIT BEFORE NOTIFICATION
        await session.commit()

        # 6. Notify the seller
        if is_display:
            seller_text = _("return_quick_seller_samples", id=return_order.id, sku=original_order.product.sku, qty=quantity)
        else:
            seller_text = _("return_quick_seller_goods", id=return_order.id, sku=original_order.product.sku, qty=quantity)
        
        await callback.message.edit_text(seller_text, parse_mode="HTML")
        
        # 7. Notify the warehouse
        notif_svc = NotificationService(callback.bot, session)
        await notif_svc.notify_warehouse(
            text=lambda _t: _t(
                "return_quick_wh_title",
                id=return_order.id,
                type=_t("return_type_samples") if is_display else _t("return_type_goods"),
                store=user.store.name if user.store and user.store.name else _t("store_label"),
                sku=original_order.product.sku,
                qty=quantity,
                note=_t("return_debt_note") if not is_display else ""
            ),
            reply_markup=lambda _t: warehouse_return_kb(return_order.id, _=_t)
        )

    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        print(f"Error in quick return_order: {e}")
    finally:
        await callback.answer()
