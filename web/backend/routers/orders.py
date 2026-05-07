from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.enums import OrderStatus
from app.models.order import Order
from app.services.order_service import OrderService
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.orders import OrderCreate, OrderOut, WarehouseDispatchCreate

from app.bot.bot import bot
from app.services.notification_service import NotificationService
from app.bot.keyboards.inline import delivery_confirm_kb, batch_delivery_confirm_kb

router = APIRouter(prefix="/orders", tags=["Orders"])


def _ensure_order_access(current_user, order: Order) -> None:
    from app.models.enums import UserRole

    if current_user.role == UserRole.SELLER and current_user.store_id != order.store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for this order",
        )


def _ensure_roles(current_user, allowed_roles: set) -> None:
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

@router.get(
    "",
    response_model=list[OrderOut],
    summary="Список заказов",
    description="Возвращает заказы с фильтрами по статусу, магазину и дате.",
)
async def list_orders(
    session: SessionDep,
    current_user: CurrentUser,
    store_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[OrderOut]:
    stmt = (
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    # Filtering logic
    from app.models.enums import UserRole
    if current_user.role == UserRole.SELLER:
        stmt = stmt.where(Order.store_id == current_user.store_id)
    elif store_id is not None:
        stmt = stmt.where(Order.store_id == store_id)

    if status == "active":
        active_statuses = [
            OrderStatus.PENDING,
            OrderStatus.RETURN_PENDING,
            OrderStatus.DISPLAY_RETURN_PENDING,
            OrderStatus.PARTIAL_APPROVAL_PENDING,
        ]
        stmt = stmt.where(Order.status.in_(active_statuses))
    elif status:
        try:
            # Check if it's a valid OrderStatus enum value
            enum_status = OrderStatus(status)
            stmt = stmt.where(Order.status == enum_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")

    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


@router.get(
    "/{order_id}",
    response_model=OrderOut,
    summary="Детали заказа",
)
async def get_order(
    order_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    _ensure_order_access(current_user, order)
    return order


@router.post(
    "",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать заказ (Продавец)",
)
async def create_order(
    body: OrderCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    from app.models.enums import UserRole
    store_id = current_user.store_id if current_user.role == UserRole.SELLER else body.store_id
    if store_id is None:
        raise HTTPException(status_code=400, detail="store_id required")

    order_svc = OrderService(session)
    try:
        order = await order_svc.create_order(
            store_id=store_id,
            product_id=body.product_id,
            quantity=body.quantity,
            batch_id=body.batch_id,
        )
        await session.commit()
        await session.refresh(order)
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id == order.id)
    )
    return result.scalar_one()


@router.post(
    "/dispatch-from-warehouse",
    response_model=list[OrderOut],
    status_code=status.HTTP_201_CREATED,
    summary="Отправить заказ в магазин (Складщик)",
    description="Складщик создаёт партию заказов и отгружает её в магазин. Продавец подтверждает приём в Telegram.",
)
async def dispatch_from_warehouse(
    body: WarehouseDispatchCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[OrderOut]:
    from app.models.enums import UserRole
    from app.services.store_service import StoreService

    _ensure_roles(current_user, {UserRole.WAREHOUSE, UserRole.OWNER, UserRole.ADMIN})

    if not body.items:
        raise HTTPException(status_code=400, detail="No items to dispatch")

    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="Main warehouse not found")
    if body.store_id == warehouse_id:
        raise HTTPException(status_code=400, detail="Cannot dispatch to the warehouse itself")

    from app.models.store import Store as StoreModel
    target_store = await session.get(StoreModel, body.store_id)
    if target_store is None:
        raise HTTPException(status_code=404, detail="Target store not found")

    items = [{"product_id": it.product_id, "quantity": it.quantity} for it in body.items]

    order_svc = OrderService(session)
    try:
        created = await order_svc.dispatch_from_warehouse(
            warehouse_store_id=warehouse_id,
            target_store_id=body.store_id,
            items=items,
        )
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        import logging
        logging.error(f"dispatch_from_warehouse error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    # Reload with relationships
    order_ids = [o.id for o in created]
    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id.in_(order_ids))
        .order_by(Order.id)
    )
    orders = list(result.scalars().unique().all())

    if orders:
        batch_id = orders[0].batch_id
        items_text = "\n".join([f"• {o.product.sku} — {o.quantity} шт" for o in orders])

        try:
            notif_svc = NotificationService(bot, session)
            await notif_svc.notify_sellers(
                store_id=body.store_id,
                text=lambda _t: _t("order_batch_accepted_seller", items=items_text),
                reply_markup=lambda _t: batch_delivery_confirm_kb(batch_id, _=_t),
            )
        except Exception as e:
            import logging
            logging.error(f"Failed to notify sellers about warehouse dispatch: {e}")

    return orders


@router.put(
    "/{order_id}/dispatch",
    response_model=OrderOut,
    summary="Отгрузить заказ (Складщик)",
)
async def dispatch_order(
    order_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    from app.models.enums import UserRole
    from app.services.store_service import StoreService
    _ensure_roles(current_user, {UserRole.WAREHOUSE, UserRole.OWNER, UserRole.ADMIN})
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="Main warehouse not found")

    order_svc = OrderService(session)
    try:
        # Full dispatch
        order = await order_svc.dispatch_order(order_id, warehouse_store_id=warehouse_id)
        await session.commit()

        # Notify seller via Telegram
        notif_svc = NotificationService(bot, session)
        await notif_svc.notify_sellers(
            store_id=order.store_id,
            text=lambda _t: _t("order_dispatch_notif_seller", id=order.id, qty=order.quantity),
            reply_markup=lambda _t: delivery_confirm_kb(order.id, order.quantity, _=_t),
        )

        try:
            await notif_svc.clear_order_notifications(
                order_id=order.id,
                new_text=f"✅ Заказ #{order.id} отгружен через веб-панель."
            )
        except Exception as e:
            import logging
            logging.error(f"Error clearing notifications: {e}")

    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id == order_id)
    )
    return result.scalar_one()


@router.put(
    "/{order_id}/deliver",
    response_model=OrderOut,
    summary="Принять доставку (Продавец)",
)
async def deliver_order(
    order_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    from app.models.enums import UserRole
    _ensure_roles(current_user, {UserRole.SELLER, UserRole.OWNER, UserRole.ADMIN})
    order_check = await session.get(Order, order_id)
    if order_check is None:
        raise HTTPException(status_code=404, detail="Order not found")
    _ensure_order_access(current_user, order_check)

    order_svc = OrderService(session)
    try:
        await order_svc.deliver_order(order_id)
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id == order_id)
    )
    return result.scalar_one()


@router.put(
    "/{order_id}/reject",
    response_model=OrderOut,
    summary="Отклонить заказ (Складщик)",
)
async def reject_order(
    order_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    from app.models.enums import UserRole
    _ensure_roles(current_user, {UserRole.WAREHOUSE, UserRole.OWNER, UserRole.ADMIN})
    order_svc = OrderService(session)
    try:
        order = await order_svc.reject_order(order_id)
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    # Notify seller via Telegram (do not fail request if notification fails).
    try:
        notif_svc = NotificationService(bot, session)
        await notif_svc.notify_sellers(
            store_id=order.store_id,
            text=lambda _t: _t("order_rejected_seller_notif", id=order.id, sku=order.product.sku, qty=order.quantity)
        )
        await notif_svc.clear_order_notifications(
            order_id=order.id,
            new_text=f"❌ Заказ #{order.id} отклонен через веб-панель."
        )
    except Exception:
        pass

    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id == order_id)
    )
    return result.scalar_one()


@router.put(
    "/{order_id}/approve_return",
    response_model=OrderOut,
    summary="Принять возврат (Складщик)",
)
async def approve_return(
    order_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    from app.models.enums import UserRole
    _ensure_roles(current_user, {UserRole.WAREHOUSE, UserRole.OWNER, UserRole.ADMIN})

    from app.services.store_service import StoreService
    from app.services.transaction_service import TransactionService
    
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="Main warehouse not found")

    txn_svc = TransactionService(session)
    try:
        await txn_svc.approve_return(
            warehouse_store_id=warehouse_id,
            warehouse_user_id=current_user.id,
            order_id=order_id,
        )
        await session.commit()

        # Reload for notification
        res = await session.execute(
            select(Order).options(joinedload(Order.product)).where(Order.id == order_id)
        )
        order = res.scalar_one()

        # Notify seller
        notif_svc = NotificationService(bot, session)
        is_display = order.status == OrderStatus.DISPLAY_RETURNED
        await notif_svc.notify_sellers(
            store_id=order.store_id,
            text=lambda _t: _t("return_approved_seller_notif", type=(_t("return_type_samples_label") if is_display else _t("return_type_goods_label")), id=order_id),
        )

        try:
            await notif_svc.clear_order_notifications(
                order_id=order.id,
                new_text=f"✅ Возврат #{order.id} принят через веб-панель."
            )
        except Exception as e:
            import logging
            logging.error(f"Error clearing notifications: {e}")

    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id == order_id)
    )
    return result.scalar_one()


@router.put(
    "/{order_id}/reject_return",
    response_model=OrderOut,
    summary="Отклонить возврат (Складщик)",
)
async def reject_return(
    order_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    from app.models.enums import UserRole
    _ensure_roles(current_user, {UserRole.WAREHOUSE, UserRole.OWNER, UserRole.ADMIN})

    from app.services.transaction_service import TransactionService
    txn_svc = TransactionService(session)
    try:
        await txn_svc.reject_return(order_id=order_id)
        await session.commit()

        # Reload for notification
        res = await session.execute(
            select(Order).where(Order.id == order_id)
        )
        order = res.scalar_one()

        # Notify seller
        notif_svc = NotificationService(bot, session)
        await notif_svc.notify_sellers(
            store_id=order.store_id,
            text=lambda _t: _t("return_rejected_seller_notif", id=order_id),
        )

        try:
            await notif_svc.clear_order_notifications(
                order_id=order.id,
                new_text=f"❌ Возврат #{order.id} отклонен через веб-панель."
            )
        except Exception as e:
            import logging
            logging.error(f"Error clearing notifications: {e}")

    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id == order_id)
    )
    return result.scalar_one()
