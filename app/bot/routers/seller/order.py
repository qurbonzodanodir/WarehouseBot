from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


import uuid

from app.bot.keyboards.inline import (
    catalog_kb, 
    order_action_kb, 
    delivery_accepted_kb, 
    delivery_confirm_kb,
    cart_action_kb,
    batch_order_action_kb
)
from app.bot.states.states import OrderFlow
from app.models.product import Product
from app.models.user import User
from app.models.store import Store
from app.services import NotificationService, OrderService, ProductService
from app.bot.routers.seller.common import MENU_TEXTS
from typing import Any
router = Router(name="seller.order")


@router.message(F.text.in_({"🛒 Заказ", "🛒 Дархост"}))
async def start_order(
    message: Message, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    await state.clear()
    order_svc = OrderService(session)
    items = await order_svc.get_available_products(store_id=user.store_id)
    if not items:
        await message.answer(_("order_empty_cat"))
        return

    await message.answer(
        _("order_title"),
        parse_mode="HTML",
        reply_markup=catalog_kb(
            items, page=0, callback_prefix="order:page", item_callback_prefix="order:select", _=_
        ),
    )
    await state.set_state(OrderFlow.select_product)


@router.message(OrderFlow.select_product, F.text)
async def search_product(
    message: Message, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    if message.text.strip() in MENU_TEXTS:
        await state.clear()
        return

    from app.services import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    
    if not warehouse_id:
        await message.answer(_("wh_not_found"))
        return

    # Check if product is in VITRINE AND in STOCK at WAREHOUSE
    from app.models.inventory import Inventory
    from sqlalchemy.orm import aliased
    WhInventory = aliased(Inventory)
    StoreInventory = aliased(Inventory)

    clean_query = message.text.strip().lower().replace(" ", "").replace("-", "")
    from app.services.product_service import ProductService
    clean_sku = ProductService._clean_col(Product.sku)

    stmt = (
        select(Product)
        .join(WhInventory, (Product.id == WhInventory.product_id) & (WhInventory.store_id == warehouse_id))
        .join(StoreInventory, (Product.id == StoreInventory.product_id) & (StoreInventory.store_id == user.store_id))
        .where(
            Product.is_active.is_(True),
            WhInventory.quantity > 0,
            clean_sku.ilike(f"%{clean_query}%")
        )
    )
    
    result = await session.execute(stmt)
    matches = list(result.scalars().all())

    if not matches:
        await message.answer(_("order_not_found_search"))
        return

    # If exactly one match, select it
    if len(matches) == 1:
        product = matches[0]
        await state.update_data(product_id=product.id)
        await message.answer(
            _("order_found", sku=product.sku),
            parse_mode="HTML",
        )
        await state.set_state(OrderFlow.enter_quantity)
        return
    else:
        await message.answer(
            _("order_search_found"),
            reply_markup=catalog_kb(
                matches,
                page=0,
                callback_prefix="order:page",
                item_callback_prefix="order:select",
                _=_
            )
        )
        return


@router.callback_query(OrderFlow.select_product, F.data.startswith("order:page:"))
async def order_page_nav(
    callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    page = int(callback.data.split(":")[-1])
    order_svc = OrderService(session)
    items = await order_svc.get_available_products(store_id=user.store_id)
    
    await callback.message.edit_reply_markup(
        reply_markup=catalog_kb(
            items, page=page, callback_prefix="order:page", item_callback_prefix="order:select", _=_
        ),
    )
    await callback.answer()


@router.callback_query(OrderFlow.select_product, F.data.startswith("order:select:"))
async def select_product(
    callback: CallbackQuery, state: FSMContext, _: Any
) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.update_data(product_id=product_id)
    await callback.message.edit_text(_("order_enter_qty"))
    await state.set_state(OrderFlow.enter_quantity)
    await callback.answer()


@router.message(OrderFlow.enter_quantity)
async def enter_order_quantity(
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
            await message.answer(_("order_not_found"))
            return

        cart = data.get("cart", [])
        found = False
        for item in cart:
            if item["product_id"] == product_id:
                item["qty"] += quantity
                found = True
                break
        if not found:
            cart.append({"product_id": product_id, "sku": product.sku, "qty": quantity})
            
        await state.update_data(cart=cart)
        
        items_text = "\n".join([_("cart_item", sku=i["sku"], qty=i["qty"]) for i in cart])
        await message.answer(
            _("cart_status", items=items_text),
            parse_mode="HTML",
            reply_markup=cart_action_kb(_=_)
        )
        await state.set_state(OrderFlow.cart_action)

    except Exception as e:
        await message.answer(_("sale_system_error"))
        print(f"Error in enter_order_quantity: {e}")


@router.callback_query(OrderFlow.cart_action, F.data == "cart:add_more")
async def cart_add_more(callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession, _: Any) -> None:
    order_svc = OrderService(session)
    items = await order_svc.get_available_products(store_id=user.store_id)
    if not items:
        await callback.message.edit_text(_("order_empty_cat"))
        return

    await callback.message.edit_text(
        _("order_title"),
        parse_mode="HTML",
        reply_markup=catalog_kb(
            items, page=0, callback_prefix="order:page", item_callback_prefix="order:select", _=_
        ),
    )
    await state.set_state(OrderFlow.select_product)


@router.callback_query(OrderFlow.cart_action, F.data == "cart:clear")
async def cart_clear(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await state.update_data(cart=[])
    await callback.message.edit_text(_("cart_cleared"))
    await state.clear()


@router.callback_query(OrderFlow.cart_action, F.data == "cart:send")
async def cart_send(callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession, _: Any) -> None:
    data = await state.get_data()
    cart = data.get("cart", [])
    if not cart:
        await callback.message.edit_text(_("cart_cleared"))
        await state.clear()
        return

    batch_id = uuid.uuid4().hex[:12]
    order_svc = OrderService(session)
    
    try:
        for item in cart:
            await order_svc.create_order(
                store_id=user.store_id,
                product_id=item["product_id"],
                quantity=item["qty"],
                batch_id=batch_id,
            )
            
        await session.commit()
        
        notif_svc = NotificationService(callback.bot, session)
        store_name = user.store.name if user.store else "Магазин"
        
        items_text = "\n".join([_("cart_item", sku=i["sku"], qty=i["qty"]) for i in cart])
        
        await notif_svc.notify_warehouse(
            text=lambda _t: _t("order_batch_notif_new", store=(_t("store_label") if getattr(user, "store_id", None) else _t("unknown")), items=items_text),
            reply_markup=lambda _t: batch_order_action_kb(batch_id, _=_t)
        )

        await callback.message.edit_text(
            _("order_batch_created")
        )
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=_(str(e))))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        print(f"Error in cart_send: {e}")

    await state.clear()


@router.callback_query(F.data.startswith("order:accept:"))
async def accept_delivery(
    callback: CallbackQuery, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        order_svc = OrderService(session)
        order = await order_svc.deliver_order(order_id)
        
        # COMMIT BEFORE UI UPDATE
        await session.commit()

        await callback.message.edit_text(
            _("order_accepted_msg", id=order.id, qty=order.quantity),
            reply_markup=delivery_accepted_kb(order.id, _=_)
        )
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        print(f"Error in accept_delivery: {e}")
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:batch_accept:"))
async def batch_accept_delivery(
    callback: CallbackQuery, session: AsyncSession, _: Any
) -> None:
    batch_id = callback.data.split(":")[-1]
    try:
        order_svc = OrderService(session)
        orders = await order_svc.get_batch_orders(batch_id)
        
        import logging
        logging.getLogger("uvicorn.error").warning(f"BATCH_ACCEPT: Found {len(orders)} orders for batch {batch_id}")
        
        from app.models.enums import OrderStatus
        delivered_info = []
        for order in orders:
            status_val = order.status.value if hasattr(order.status, "value") else str(order.status)
            logging.getLogger("uvicorn.error").warning(f"BATCH_ACCEPT: Order {order.id} status is {order.status} ({type(order.status)})")
            
            if order.status == OrderStatus.DISPATCHED or status_val.lower() == "dispatched":
                await order_svc.deliver_order(order.id)
                delivered_info.append((order.id, order.quantity))
                logging.getLogger("uvicorn.error").warning(f"BATCH_ACCEPT: Delivered {order.id}")
                
        if not delivered_info:
            await callback.message.edit_text("⚠️ Эта партия уже была обработана или пуста.")
            await callback.answer()
            return
            
        await session.commit()

        await callback.message.edit_text(
            _("batch_delivery_success")
        )
        
        # Send individual management messages with action buttons (Sell / Return)
        for oid, qty in delivered_info:
            await callback.message.answer(
                _("order_accepted_msg", id=oid, qty=qty),
                reply_markup=delivery_accepted_kb(oid, _=_)
            )
            
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        print(f"Error in batch_accept_delivery: {e}")
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:partial_accept:"))
async def partial_accept(
    callback: CallbackQuery, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        from app.services import StoreService
        store_svc = StoreService(session)
        warehouse_store_id = await store_svc.get_main_warehouse_id()
        if not warehouse_store_id:
            await callback.message.edit_text(_("wh_not_found"))
            await callback.answer()
            return

        order_svc = OrderService(session)
        order = await order_svc.accept_partial_dispatch(
            order_id, warehouse_store_id=warehouse_store_id
        )
        
        # COMMIT BEFORE NOTIFICATION
        await session.commit()
        
        await callback.message.edit_text(
            _("order_partial_accept_msg", id=order.id, qty=order.quantity)
        )

        notif_svc = NotificationService(callback.bot, session)
        await notif_svc.notify_warehouse(
            text=lambda _t: _t("order_partial_notif_wh", id=order.id, qty=order.quantity),
            reply_markup=None,
        )
        
        await notif_svc.notify_sellers(
            store_id=order.store_id,
            text=lambda _t: _t("order_delivery_notif", id=order.id, qty=order.quantity),
            reply_markup=lambda _t: delivery_confirm_kb(order.id, order.quantity, _=_t),
        )

    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        print(f"Error in partial_accept: {e}")
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:partial_reject:"))
async def partial_reject(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        from app.services import StoreService
        store_svc = StoreService(session)
        warehouse_id = await store_svc.get_main_warehouse_id()
        if not warehouse_id:
            await callback.message.edit_text(_("wh_not_found"))
            await callback.answer()
            return
        
        order_svc = OrderService(session)
        order = await order_svc.reject_partial_dispatch(
            order_id, warehouse_store_id=warehouse_id
        )
        
        # COMMIT BEFORE NOTIFICATION
        await session.commit()
        
        await callback.message.edit_text(
            _("order_partial_reject_msg", id=order.id)
        )

        notif_svc = NotificationService(callback.bot, session)
        await notif_svc.notify_warehouse(
            text=lambda _t: _t("order_partial_reject_wh", id=order.id),
            reply_markup=None,
        )

    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        print(f"Error in partial_reject: {e}")
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:partial_accept_batch:"))
async def partial_accept_batch(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    batch_id = callback.data.split(":")[-1]
    try:
        from app.services import StoreService
        store_svc = StoreService(session)
        warehouse_id = await store_svc.get_main_warehouse_id()
        if not warehouse_id:
            await callback.message.edit_text(_("wh_not_found"))
            await callback.answer()
            return
            
        order_svc = OrderService(session)
        
        # 1. Fetch available again to ensure nothing changed
        avail = await order_svc.check_batch_availability(batch_id, warehouse_id)
        if not avail["orders"]:
            await callback.message.edit_text("Заявка пуста или уже обработана.")
            await callback.answer()
            return
            
        # Check if the proposal is still valid
        from app.models.enums import OrderStatus
        for order in avail["orders"]:
            if order.status != OrderStatus.PARTIAL_APPROVAL_PENDING:
                await callback.message.edit_text("⚠️ Эта заявка уже была обработана.")
                await callback.answer()
                return

        # If literally NOTHING is available, we cannot create an adjusted batch!
        if not avail["available"] and not avail["partial"]:
            for order in avail["orders"]:
                order.status = OrderStatus.REJECTED
            await session.commit()
            
            items_text = "\n".join([_("cart_item", sku=o.product.sku, qty=o.quantity) for o in avail["orders"]])
            await callback.message.edit_text("❌ Доступных товаров больше нет. Заявка отменена целиком.")
            
            notif_svc = NotificationService(callback.bot, session)
            store_name = user.store.name if user.store else str(user.store_id)
            await notif_svc.notify_warehouse(
                text=lambda _t: f"❌ <b>Продавец {store_name} отменил заявку (нет доступных товаров)!</b>\n\nПозиции:\n{items_text}",
                reply_markup=None
            )
            await callback.answer()
            return

        # 2. Adjust batch
        import logging
        logging.getLogger("uvicorn.error").warning(f"PARTIAL_ACCEPT: old batch={batch_id}, calling create_adjusted_batch...")
        new_batch_id = await order_svc.create_adjusted_batch(batch_id, avail)
        await session.commit()
        logging.getLogger("uvicorn.error").warning(f"PARTIAL_ACCEPT: new batch={new_batch_id}, committed!")
        
        # 3. Notify seller & warehouse
        await callback.message.edit_text("✅ Заявка скорректирована и отправлена на склад.")
        
        notif_svc = NotificationService(callback.bot, session)
        store_name = user.store.name if user.store else str(user.store_id)
        
        new_orders = await order_svc.get_batch_orders(new_batch_id)
        logging.getLogger("uvicorn.error").warning(f"PARTIAL_ACCEPT: fetched {len(new_orders)} orders for new batch {new_batch_id}")
        
        items_text = "\n".join([_("cart_item", sku=o.product.sku, qty=o.quantity) for o in new_orders])
        
        await notif_svc.notify_warehouse(
            text=lambda _t: _t("order_batch_notif_new", store=store_name, items=items_text),
            reply_markup=lambda _t: batch_order_action_kb(new_batch_id, _=_t)
        )
        
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        import traceback
        traceback.print_exc()
        print(f"Error in partial_accept_batch: {e}")
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:partial_reject_batch:"))
async def partial_reject_batch(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    batch_id = callback.data.split(":")[-1]
    try:
        order_svc = OrderService(session)
        orders = await order_svc.get_batch_orders(batch_id)
        import logging
        
        from app.models.enums import OrderStatus
        valid = False
        for order in orders:
            if order.status == OrderStatus.PARTIAL_APPROVAL_PENDING:
                order.status = OrderStatus.REJECTED
                valid = True
                
        if not valid:
            await callback.message.edit_text("⚠️ Эта заявка уже была обработана.")
            await callback.answer()
            return
            
        await session.commit()
        
        items_text = "\n".join([_("cart_item", sku=o.product.sku, qty=o.quantity) for o in orders])
        await callback.message.edit_text("❌ Заявка отменена.")
        
        notif_svc = NotificationService(callback.bot, session)
        store_name = user.store.name if user.store else str(user.store_id)
        await notif_svc.notify_warehouse(
            text=lambda _t: f"❌ <b>Продавец {store_name} отменил заявку из-за нехватки товара!</b>\n\nПозиции:\n{items_text}",
            reply_markup=None
        )
        
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        print(f"Error in partial_reject_batch: {e}")
    finally:
        await callback.answer()
