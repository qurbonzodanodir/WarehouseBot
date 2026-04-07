from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.enums import OrderStatus
from app.models.order import Order
from app.services.order_service import OrderService
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.orders import OrderCreate, OrderOut

from app.bot.bot import bot
from app.services.notification_service import NotificationService
from app.bot.keyboards.inline import delivery_confirm_kb

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
