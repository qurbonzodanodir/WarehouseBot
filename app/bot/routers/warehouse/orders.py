from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
import logging

logger = logging.getLogger(__name__)

from app.bot.keyboards.inline import (
    delivery_confirm_kb, 
    order_action_kb, 
    partial_approval_kb
)
from app.models.user import User
from app.models.order import Order
from app.models.enums import OrderStatus
from app.services import (
    NotificationService, 
    OrderService, 
    TransactionService,
    StoreService
)

router = Router(name="warehouse.orders")


@router.message(F.text.in_({"🔔 Запросы", "🔔 Дархостҳо"}))
async def active_requests(message: Message, session: AsyncSession, _: Any) -> None:
    order_svc = OrderService(session)
    orders = await order_svc.get_pending_orders()
    if not orders:
        await message.answer(_("requests_not_found"))
        return

    for order in orders:
        text = _(
            "requests_title",
            id=order.id,
            store=order.store.name if order.store else _("unknown"),
            sku=order.product.sku,
            qty=order.quantity
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=order_action_kb(order.id, _=_),
        )


@router.callback_query(F.data.startswith("order:dispatch:"))
async def dispatch_order_start(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        order = await session.get(Order, order_id)
        if not order:
            await callback.message.edit_text(_("order_not_found"))
            return

        # Check warehouse inventory
        store_svc = StoreService(session)
        warehouse_id = await store_svc.get_main_warehouse_id()
        if not warehouse_id:
            await callback.answer(_("warehouse_not_found"), show_alert=True)
            return

        txn_svc = TransactionService(session)
        inv = await txn_svc.get_inventory(warehouse_id, order.product_id)
        if inv is None:
            await callback.answer(
                _("stock_error_zero", sku=order.product.sku),
                show_alert=True
            )
            return
        available_qty = inv.quantity

        if available_qty == 0:
            await callback.answer(
                _("stock_error_zero", sku=order.product.sku),
                show_alert=True
            )
            return

        requested_qty = order.quantity
        order_svc = OrderService(session)
        notif_svc = NotificationService(callback.bot, session)
        
        if available_qty >= requested_qty:
            # Full dispatch
            order = await order_svc.dispatch_order(
                order_id, warehouse_store_id=warehouse_id
            )
            await session.commit()
            
            await callback.message.edit_text(
                _("order_dispatch_success", id=order.id, qty=order.quantity)
            )

            await notif_svc.notify_sellers(
                store_id=order.store_id,
                text=lambda _t: _t("order_dispatch_notif_seller", id=order.id, qty=order.quantity),
                reply_markup=lambda _t: delivery_confirm_kb(order.id, order.quantity, _=_t),
            )
        else:
            # Propose partial dispatch
            qty_to_send = available_qty
            order = await order_svc.propose_partial_dispatch(
                order_id, warehouse_store_id=warehouse_id, proposed_quantity=qty_to_send
            )
            await session.commit()
            
            await callback.message.edit_text(
                _("order_partial_wh_msg", id=order.id, requested=requested_qty, available=qty_to_send),
                parse_mode="HTML"
            )

            await notif_svc.notify_sellers(
                store_id=order.store_id,
                text=lambda _t: _t("order_partial_seller_notif", id=order.id, requested=requested_qty, available=qty_to_send),
                reply_markup=lambda _t: partial_approval_kb(order.id, _=_t),
            )

    except ValueError as e:
        await callback.message.edit_text(_("order_dispatch_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        logger.error(f"Error in dispatch_order_start: {e}", exc_info=True)
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:reject:"))
async def reject_order(
    callback: CallbackQuery, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        order_svc = OrderService(session)
        order = await order_svc.reject_order(order_id)
        await session.commit()
        await callback.message.edit_text(
            _("order_rejected_wh", id=order.id)
        )
        
        # Notify seller
        from app.services.notification_service import NotificationService
        notif_svc = NotificationService(callback.bot, session)
        await notif_svc.notify_sellers(
            store_id=order.store_id,
            text=lambda _t: _t("order_rejected_seller_notif", id=order.id, sku=order.product.sku, qty=order.quantity)
        )
    except ValueError as e:
        await callback.message.edit_text(_("error_label", error=str(e)))
    await callback.answer()

@router.callback_query(F.data.startswith("order:approve_return:"))
async def approve_return(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        order = await session.get(Order, order_id)
        if not order:
            await callback.message.edit_text(_("order_not_found"))
            return

        is_display = order.status == OrderStatus.DISPLAY_RETURN_PENDING
        store_id = order.store_id
        
        store_svc = StoreService(session)
        warehouse_id = await store_svc.get_main_warehouse_id()
        if not warehouse_id:
             await callback.answer(_("warehouse_not_found"), show_alert=True)
             return

        txn_svc = TransactionService(session)
        await txn_svc.approve_return(
            warehouse_store_id=warehouse_id,
            warehouse_user_id=user.id,
            order_id=order_id,
        )
        await session.commit()
        
        return_amount = order.price_per_item * order.quantity
        
        return_type_label = _("return_type_samples_label") if is_display else _("return_type_goods_label")
        
        await callback.message.edit_text(
            _("return_approved_wh", type=return_type_label, id=order_id)
        )

        notif_svc = NotificationService(callback.bot, session)
        await notif_svc.notify_sellers(
            store_id=store_id,
            text=lambda _t: _t("return_approved_seller_notif", type=(_t("return_type_samples_label") if is_display else _t("return_type_goods_label")), id=order_id),
            reply_markup=None,
        )

    except ValueError as e:
        await callback.message.edit_text(_("return_approve_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        logger.error(f"Error in approve_return: {e}", exc_info=True)
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:reject_return:"))
async def reject_return_request(
    callback: CallbackQuery, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        order = await session.get(Order, order_id)
        if not order:
            await callback.message.edit_text(_("order_not_found"))
            return

        store_id = order.store_id
        
        txn_svc = TransactionService(session)
        await txn_svc.reject_return(
            order_id=order_id,
        )
        await session.commit()
        await callback.message.edit_text(
            _("return_rejected_wh_msg", id=order_id)
        )

        notif_svc = NotificationService(callback.bot, session)
        await notif_svc.notify_sellers(
            store_id=store_id,
            text=lambda _t: _t("return_rejected_seller_notif", id=order_id),
            reply_markup=None,
        )

    except ValueError as e:
        await callback.message.edit_text(_("error_label", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        logger.error(f"Error in reject_return_request: {e}", exc_info=True)
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:approve_batch:"))
async def approve_batch_order(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    batch_id = callback.data.split(":")[-1]
    try:
        # Check warehouse inventory
        store_svc = StoreService(session)
        warehouse_id = await store_svc.get_main_warehouse_id()
        if not warehouse_id:
            await callback.answer(_("warehouse_not_found"), show_alert=True)
            return

        order_svc = OrderService(session)
        avail = await order_svc.check_batch_availability(batch_id, warehouse_id)
        
        available = avail["available"]
        partial = avail["partial"]
        missing = avail["missing"]
        orders = avail["orders"]
        
        if not orders:
            await callback.message.edit_text(_("batch_empty_or_processed"))
            return

        store_id = orders[0].store_id
        notif_svc = NotificationService(callback.bot, session)

        if not partial and not missing:
            # Full dispatch
            dispatched = await order_svc.dispatch_batch_order(batch_id, warehouse_store_id=warehouse_id)
            dispatched_text = "\n".join([f"• {o.product.sku} — {o.quantity} шт" for o in dispatched])
            
            await session.commit()
            await callback.message.edit_text(_("batch_dispatched_wh", batch_id=batch_id))
            
            from app.bot.keyboards.inline import batch_delivery_confirm_kb
            await notif_svc.notify_sellers(
                store_id=store_id,
                text=lambda _t: _t("order_batch_accepted_seller", items=dispatched_text),
                reply_markup=lambda _t: batch_delivery_confirm_kb(batch_id, _=_t)
            )
        else:
            # Propose partial fulfillment to seller
            from app.models.enums import OrderStatus
            for o in orders:
                o.status = OrderStatus.PARTIAL_APPROVAL_PENDING
            await session.commit()
            
            avail_text = "\n".join([f"• {i['order'].product.sku} — {i['available_qty']} шт" for i in available]) if available else "—"
            missing_text = "\n".join([f"• {i['order'].product.sku} — {i['order'].quantity} шт" for i in missing]) if missing else "—"
            
            wh_msg = (
                _("batch_partial_pending_wh", batch_id=batch_id, available=avail_text, missing=missing_text)
            )
            await callback.message.edit_text(wh_msg)
            
            from app.bot.keyboards.inline import batch_partial_proposal_kb
            await notif_svc.notify_sellers(
                store_id=store_id,
                text=lambda _t: _t("order_batch_partial_proposal", available=avail_text, missing=missing_text),
                reply_markup=lambda _t: batch_partial_proposal_kb(batch_id, _=_t)
            )
            
    except ValueError as e:
        await callback.message.edit_text(_("error_label", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        logger.error(f"Error in approve_batch_order: {e}", exc_info=True)
    finally:
        await callback.answer()

@router.callback_query(F.data.startswith("order:reject_batch:"))
async def reject_batch_order(
    callback: CallbackQuery, session: AsyncSession, _: Any
) -> None:
    batch_id = callback.data.split(":")[-1]
    try:
        order_svc = OrderService(session)
        rejected_orders = await order_svc.reject_batch_order(batch_id)
        if not rejected_orders:
            await callback.message.edit_text(_("batch_empty_or_processed"))
            return
            
        store_id = rejected_orders[0].store_id
        items_text = "\n".join([f"• {o.product.sku} — {o.quantity} шт" for o in rejected_orders])

        await callback.message.edit_text(
            _("batch_rejected_wh", batch_id=batch_id)
        )
        
        notif_svc = NotificationService(callback.bot, session)
        await notif_svc.notify_sellers(
            store_id=store_id,
            text=lambda _t: _t("order_batch_rejected_seller", items=items_text)
        )
    except Exception as e:
        await callback.message.edit_text(_("error_label", error=str(e)))
    finally:
        await callback.answer()
