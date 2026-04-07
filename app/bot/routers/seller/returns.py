from decimal import Decimal

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


def _clean_search_query(text: str) -> str:
    return text.strip().lower().replace(" ", "").replace("-", "")


async def _get_display_qty_available(
    session: AsyncSession,
    store_id: int,
    product_id: int,
) -> int:
    delivered_result = await session.execute(
        select(func.coalesce(func.sum(Order.quantity), 0)).where(
            Order.store_id == store_id,
            Order.product_id == product_id,
            Order.status == OrderStatus.DISPLAY_DELIVERED,
        )
    )
    delivered_qty = delivered_result.scalar() or 0

    reserved_result = await session.execute(
        select(func.coalesce(func.sum(Order.quantity), 0)).where(
            Order.store_id == store_id,
            Order.product_id == product_id,
            Order.status.in_(
                (
                    OrderStatus.DISPLAY_RETURN_PENDING,
                    OrderStatus.DISPLAY_RETURNED,
                )
            ),
        )
    )
    reserved_qty = reserved_result.scalar() or 0
    return max(0, delivered_qty - reserved_qty)


@router.message(F.text.in_({"↩️ Сделать возврат", "↩️ Бозгашти мол"}))
async def start_return(
    message: Message, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    await state.clear()
    order_svc = OrderService(session)
    items = await order_svc.get_store_vitrine_inventory(user.store_id, include_empty=False)
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

    order_svc = OrderService(session)
    items = await order_svc.get_store_vitrine_inventory(user.store_id, include_empty=False)
    clean_query = _clean_search_query(message.text)
    exact_match = next((item for item in items if _clean_search_query(item.product.sku) == clean_query), None)
    partial_matches = [item.product for item in items if clean_query in _clean_search_query(item.product.sku)]

    if exact_match:
        await state.update_data(product_id=exact_match.product.id)
        await message.answer(
            _("return_selected", sku=exact_match.product.sku, qty=exact_match.quantity),
            parse_mode="HTML"
        )
        await state.set_state(ReturnFlow.enter_quantity)
        return
    elif partial_matches:
        await message.answer(
            _("return_search_found"),
            reply_markup=catalog_kb(
                partial_matches,
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
    order_svc = OrderService(session)
    items = await order_svc.get_store_vitrine_inventory(user.store_id, include_empty=False)
    products = [item.product for item in items] if items else []
    
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
    order_svc = OrderService(session)
    regular_qty, display_qty = await order_svc.get_store_vitrine_product_stock(user.store_id, product_id)
    qty = regular_qty + display_qty
    
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

        order_svc = OrderService(session)
        regular_qty, display_qty = await order_svc.get_store_vitrine_product_stock(
            user.store_id, product_id
        )
        total_qty = regular_qty + display_qty
        if total_qty < quantity:
            await message.answer(_("return_enter_qty", qty=total_qty))
            return

        items_to_return = []
        remaining_qty = quantity

        # Priority 1: Regular
        if regular_qty > 0:
            take = min(regular_qty, remaining_qty)
            if take > 0:
                items_to_return.append({"is_display": False, "qty": take})
                remaining_qty -= take
                
        # Priority 2: Display
        if display_qty > 0 and remaining_qty > 0:
            take = min(display_qty, remaining_qty)
            if take > 0:
                items_to_return.append({"is_display": True, "qty": take})
                remaining_qty -= take

        txn_svc = TransactionService(session)
        notif_svc = NotificationService(message.bot, session)

        for item in items_to_return:
            is_display = item["is_display"]
            qty = item["qty"]

            # 1. Создаем заказ с правильным статусом и фиксируем цену
            price_per_item = Decimal("0") if is_display else product.price
            return_order = Order(
                store_id=user.store_id,
                product_id=product_id,
                quantity=qty,
                price_per_item=price_per_item,
                total_price=price_per_item * qty,
                status=OrderStatus.DISPLAY_RETURN_PENDING if is_display else OrderStatus.RETURN_PENDING,
            )
    
            session.add(return_order)
            await session.flush()
            
            # 2. Передаем в транзакцию возврата
            await txn_svc.initiate_return(
                store_id=user.store_id,
                user_id=user.id,
                product_id=product_id,
                quantity=qty,
                order_id=return_order.id,
            )
            
            # 3. Отправляем уведомление на склад
            await notif_svc.notify_warehouse(
                text=lambda _t, ret=return_order, is_d=is_display, q=qty: _t(
                    "return_notif_wh",
                    type=_t("return_type_samples") if is_d else _t("return_type_goods"),
                    store=user.store.name if user.store and user.store.name else _t("store_label"),
                    id=ret.id,
                    sku=product.sku,
                    qty=q,
                    note="" if is_d else _t("return_notif_wh_instr")
                ),
                reply_markup=lambda _t, ret=return_order: warehouse_return_kb(ret.id, _=_t)
            )

        # COMMIT ALL AT ONCE
        await session.commit()
        
        # 4. Сообщение продавцу
        if len(items_to_return) > 1:
            reg_qty = items_to_return[0]["qty"]
            disp_qty = items_to_return[1]["qty"]
            seller_msg = f"✅ Вы возвращаете {quantity} шт:\n• {reg_qty} как обычный товар\n• {disp_qty} как образец.\n\nОтправлены 2 раздельные заявки на склад."
        else:
            if items_to_return[0]["is_display"]:
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
        if original_order.store_id != user.store_id:
            await callback.answer(_("order_not_found"), show_alert=True)
            return
        if original_order.status not in (OrderStatus.DELIVERED, OrderStatus.DISPLAY_DELIVERED):
            await callback.answer(_("sale_error", error=_("return_invalid_status")), show_alert=True)
            return

        product_id = original_order.product_id
        quantity = original_order.quantity

        # 2. Check if the store actually has this quantity available
        # 3. Determine if this should be a display return
        is_display = (original_order.status == OrderStatus.DISPLAY_DELIVERED)
        order_svc = OrderService(session)
        regular_qty, display_qty = await order_svc.get_store_vitrine_product_stock(
            user.store_id, product_id
        )
        available_qty = display_qty if is_display else regular_qty
        if available_qty < quantity:
            await callback.answer(
                _("return_quick_not_enough"),
                show_alert=True
            )
            return

        # 4. Create a new return order
        return_order = Order(
            store_id=user.store_id,
            product_id=product_id,
            quantity=quantity,
            price_per_item=original_order.price_per_item,
            total_price=original_order.price_per_item * quantity,
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
