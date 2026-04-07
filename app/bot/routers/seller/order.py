from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession


import uuid
import logging

logger = logging.getLogger(__name__)

from app.bot.keyboards.inline import (
    catalog_kb,
    delivery_accepted_kb,
    delivery_confirm_kb,
    cart_action_kb,
    batch_order_action_kb,
    batch_delivery_accepted_kb,
)
from app.bot.states.states import OrderFlow
from app.models.product import Product
from typing import Any
from app.models.order import Order
from app.models.user import User
from app.services import NotificationService, OrderService
from app.bot.routers.seller.common import MENU_TEXTS
router = Router(name="seller.order")


def _clean_search_query(text: str) -> str:
    return text.strip().lower().replace(" ", "").replace("-", "")


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

    order_svc = OrderService(session)
    items = await order_svc.get_available_products(store_id=user.store_id)
    clean_query = _clean_search_query(message.text)
    matches = [
        product
        for product in items
        if clean_query in _clean_search_query(product.sku)
    ]

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
        logger.error(f"Error in enter_order_quantity: {e}", exc_info=True)

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
        store_name = user.store.name if user.store else _("store_label")
        
        items_text = "\n".join([_("cart_item", sku=i["sku"], qty=i["qty"]) for i in cart])
        
        await notif_svc.notify_warehouse(
            text=lambda _t: _t("order_batch_notif_new", store=store_name, items=items_text),
            reply_markup=lambda _t: batch_order_action_kb(batch_id, _=_t)
        )

        await callback.message.edit_text(
            _("order_batch_created")
        )
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=_(str(e))))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        logger.error(f"Error in cart_send: {e}", exc_info=True)

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
        logger.error(f"Error in accept_delivery: {order_id=}, {e}", exc_info=True)
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
        
        from app.models.enums import OrderStatus
        delivered_info = []
        for order in orders:
            status_val = order.status.value if hasattr(order.status, "value") else str(order.status)
            
            if order.status == OrderStatus.DISPATCHED or status_val.lower() == "dispatched":
                await order_svc.deliver_order(order.id)
                delivered_info.append((order.id, order.quantity))
                
        if not delivered_info:
            await callback.message.edit_text(_("batch_empty_or_processed"))
            await callback.answer()
            return
            
        await session.commit()

        await callback.message.edit_text(
            _("batch_delivery_success"),
            reply_markup=batch_delivery_accepted_kb(batch_id, _=_)
        )
            
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        logger.error(f"Error in batch_accept_delivery: {batch_id=}, {e}", exc_info=True)
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:sell_batch:"))
async def sell_entire_batch(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    batch_id = callback.data.split(":")[-1]
    try:
        from app.services import TransactionService
        order_svc = OrderService(session)
        txn_svc = TransactionService(session)
        orders = await order_svc.get_batch_orders(batch_id)
        
        from app.models.enums import OrderStatus
        sold_count = 0
        
        for order in orders:
            status_val = order.status.value if hasattr(order.status, "value") else str(order.status)
            if order.status == OrderStatus.DELIVERED or status_val.lower() == "delivered":
                await txn_svc.record_sale(
                    store_id=user.store_id,
                    user_id=user.id,
                    product_id=order.product_id,
                    quantity=order.quantity,
                    price_per_unit=order.price_per_item,
                    order_id=order.id
                )
                sold_count += 1
                
        if sold_count == 0:
            await callback.message.edit_text(_("batch_already_processed"))
            await callback.answer()
            return

        await session.commit()
        await callback.message.edit_text(_("sell_batch_success"))
        
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        logger.error(f"Error in sell_entire_batch: {batch_id=}, {e}", exc_info=True)
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:return_batch:"))
async def return_entire_batch(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    batch_id = callback.data.split(":")[-1]
    try:
        from app.services import TransactionService, NotificationService
        from app.bot.keyboards.inline import warehouse_return_kb
        order_svc = OrderService(session)
        orders = await order_svc.get_batch_orders(batch_id)
        
        from app.models.enums import OrderStatus
        returned_count = 0
        notif_svc = NotificationService(callback.bot, session)
        txn_svc = TransactionService(session)
        
        for original_order in orders:
            status_val = original_order.status.value if hasattr(original_order.status, "value") else str(original_order.status)
            if original_order.status == OrderStatus.DELIVERED or status_val.lower() == "delivered" or original_order.status == OrderStatus.DISPLAY_DELIVERED or status_val.lower() == "display_delivered":
                is_display = (original_order.status == OrderStatus.DISPLAY_DELIVERED or status_val.lower() == "display_delivered")
                product_id = original_order.product_id
                quantity = original_order.quantity
                
                # Check stock
                regular_qty, display_qty = await order_svc.get_store_vitrine_product_stock(
                    user.store_id, product_id
                )
                available_qty = display_qty if is_display else regular_qty
                if available_qty < quantity:
                    continue  # skip if they don't have enough anymore

                # Create return order
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

                # Initiate return
                await txn_svc.initiate_return(
                    store_id=user.store_id,
                    user_id=user.id,
                    product_id=product_id,
                    quantity=quantity,
                    order_id=return_order.id,
                )
                
                # Send explicit notification to warehouse per order
                if not is_display:
                    p = original_order.product.sku if original_order.product else str(product_id)
                    await notif_svc.notify_warehouse(
                        text=lambda _t, _ret=return_order, _p=p, _q=quantity, _is_disp=is_display: _t(
                            "return_quick_wh_title",
                            id=_ret.id,
                            type=_t("return_type_samples") if _is_disp else _t("return_type_goods"),
                            store=user.store.name if user.store and user.store.name else _t("store_label"),
                            sku=_p,
                            qty=_q,
                            note=_t("return_debt_note") if not _is_disp else ""
                        ),
                        reply_markup=lambda _t, _ret=return_order: warehouse_return_kb(_ret.id, _=_t)
                    )
                else:
                    p = original_order.product.sku if original_order.product else str(product_id)
                    await notif_svc.notify_warehouse(
                        text=lambda _t, _ret=return_order, _p=p, _q=quantity, _is_disp=is_display: _t(
                            "return_quick_wh_title",
                            id=_ret.id,
                            type=_t("return_type_samples") if _is_disp else _t("return_type_goods"),
                            store=user.store.name if user.store and user.store.name else _t("store_label"),
                            sku=_p,
                            qty=_q,
                            note=""
                        ),
                        reply_markup=lambda _t, _ret=return_order: warehouse_return_kb(_ret.id, _=_t)
                    )
                returned_count += 1
                
        if returned_count == 0:
            await callback.message.edit_text(_("return_quick_not_enough"))
            await callback.answer()
            return

        await session.commit()
        await callback.message.edit_text(_("return_confirm_msg_goods")) # General success message
        
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        logger.error(f"Error in return_entire_batch: {batch_id=}, {e}", exc_info=True)
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
        logger.error(f"Error in partial_accept: {order_id=}, {e}", exc_info=True)
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
            _("order_partial_reject_msg", id=order_id)
        )

        notif_svc = NotificationService(callback.bot, session)
        await notif_svc.notify_warehouse(
            text=lambda _t: _t("order_partial_reject_wh", id=order_id),
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
            await callback.message.edit_text(_("batch_empty_or_processed"))
            await callback.answer()
            return
            
        # Check if the proposal is still valid
        from app.models.enums import OrderStatus
        for order in avail["orders"]:
            if order.status != OrderStatus.PARTIAL_APPROVAL_PENDING:
                await callback.message.edit_text(_("batch_already_processed"))
                await callback.answer()
                return

        # If literally NOTHING is available, we cannot create an adjusted batch!
        if not avail["available"]:
            for order in avail["orders"]:
                order.status = OrderStatus.REJECTED
            await session.commit()
            
            items_text = "\n".join([_("cart_item", sku=o.product.sku, qty=o.quantity) for o in avail["orders"]])
            await callback.message.edit_text(_("batch_no_available_cancelled"))
            
            notif_svc = NotificationService(callback.bot, session)
            store_name = user.store.name if user.store else str(user.store_id)
            await notif_svc.notify_warehouse(
                text=lambda _t: _t("batch_cancelled_no_stock_wh", store=store_name, items=items_text),
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
        await callback.message.edit_text(_("batch_adjusted_sent"))
        
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
        
        from app.models.enums import OrderStatus
        valid = False
        for order in orders:
            if order.status == OrderStatus.PARTIAL_APPROVAL_PENDING:
                order.status = OrderStatus.REJECTED
                valid = True
                
        if not valid:
            await callback.message.edit_text(_("batch_already_processed"))
            await callback.answer()
            return
            
        await session.commit()
        
        items_text = "\n".join([_("cart_item", sku=o.product.sku, qty=o.quantity) for o in orders])
        await callback.message.edit_text(_("batch_cancelled"))
        
        notif_svc = NotificationService(callback.bot, session)
        store_name = user.store.name if user.store else str(user.store_id)
        await notif_svc.notify_warehouse(
            text=lambda _t: _t("batch_cancelled_shortage_wh", store=store_name, items=items_text),
            reply_markup=None
        )
        
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        print(f"Error in partial_reject_batch: {e}")
    finally:
        await callback.answer()
