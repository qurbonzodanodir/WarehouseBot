from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.enums import OrderStatus
from app.models.order import Order
from app.services.order_service import OrderService
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.orders import OrderCreate, OrderOut, ReturnRequestCreate, WarehouseDispatchCreate

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
    "/returns",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Вернуть товар из магазина на склад",
    description="Owner/warehouse/admin возвращает товар сразу без подтверждения продавца.",
)
async def create_return(
    body: ReturnRequestCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    from app.models.debt_ledger import DebtLedger
    from app.models.enums import DebtLedgerReason, StockMovementType, UserRole
    from app.models.product import Product
    from app.models.store import Store as StoreModel
    from app.services.store_service import StoreService
    from app.services.transaction_service import TransactionService

    if body.quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")

    if current_user.role == UserRole.SELLER:
        if current_user.store_id != body.from_store_id:
            raise HTTPException(status_code=403, detail="Access denied for this store")
        raise HTTPException(
            status_code=400,
            detail="Seller return requests are supported from Telegram. Use owner/warehouse web return here.",
        )

    _ensure_roles(current_user, {UserRole.WAREHOUSE, UserRole.OWNER, UserRole.ADMIN})

    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="Main warehouse not found")
    if body.from_store_id == warehouse_id:
        raise HTTPException(status_code=400, detail="Cannot return from the warehouse to itself")

    store = await session.get(StoreModel, body.from_store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    product = await session.get(Product, body.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    txn_svc = TransactionService(session)

    try:
        display_inv = await txn_svc._get_display_inventory(body.from_store_id, body.product_id, lock=True)
        regular_inv = await txn_svc._get_inventory(body.from_store_id, body.product_id, lock=True)

        display_qty = display_inv.quantity if display_inv else 0
        regular_qty = regular_inv.quantity if regular_inv else 0
        use_display = body.prefer_display and display_qty >= body.quantity

        if use_display:
            if display_inv is None:
                raise ValueError("Display inventory not found")
            source_inv = display_inv
            status_to_set = OrderStatus.DISPLAY_RETURNED
            movement_type = StockMovementType.DISPLAY_RETURN
            price = product.effective_store_price
        elif regular_qty >= body.quantity:
            if regular_inv is None:
                raise ValueError("Inventory not found")
            source_inv = regular_inv
            status_to_set = OrderStatus.RETURNED
            movement_type = StockMovementType.RETURN_TO_WAREHOUSE
            price = product.effective_store_price
        elif display_qty >= body.quantity:
            if display_inv is None:
                raise ValueError("Display inventory not found")
            source_inv = display_inv
            status_to_set = OrderStatus.DISPLAY_RETURNED
            movement_type = StockMovementType.DISPLAY_RETURN
            price = product.effective_store_price
        else:
            available = display_qty + regular_qty
            raise ValueError(
                f"Недостаточно товара для возврата: в наличии {available}, нужно {body.quantity}."
            )

        source_inv.quantity -= body.quantity
        if status_to_set == OrderStatus.DISPLAY_RETURNED and source_inv.quantity <= 0:
            await session.delete(source_inv)
        movement_to_store_id = None
        if status_to_set != OrderStatus.DISPLAY_RETURNED:
            warehouse_inv = await txn_svc._get_or_create_inventory(warehouse_id, body.product_id, lock=True)
            warehouse_inv.quantity += body.quantity
            movement_to_store_id = warehouse_id

        order = Order(
            store_id=body.from_store_id,
            product_id=body.product_id,
            quantity=body.quantity,
            price_per_item=price,
            total_price=price * body.quantity,
            status=status_to_set,
        )
        session.add(order)
        await session.flush()

        await txn_svc.record_stock_movement(
            product_id=body.product_id,
            quantity=body.quantity,
            movement_type=movement_type,
            from_store_id=body.from_store_id,
            to_store_id=movement_to_store_id,
            user_id=current_user.id,
        )

        if status_to_set == OrderStatus.RETURNED and order.total_price > 0:
            await txn_svc.record_debt_ledger(
                store_id=body.from_store_id,
                amount_change=-order.total_price,
                reason=DebtLedgerReason.RETURN_APPROVED,
                description=f"Возврат owner #{order.id} на склад (SKU: {product.sku}, {body.quantity} шт.)",
            )
        elif status_to_set == OrderStatus.DISPLAY_RETURNED:
            ledger = DebtLedger(
                store_id=body.from_store_id,
                amount_change=0,
                balance_after=store.current_debt,
                reason=DebtLedgerReason.RETURN_APPROVED,
                description=f"Возврат витрины owner #{order.id} на фирму (SKU: {product.sku}, {body.quantity} шт.)",
            )
            session.add(ledger)

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
        .where(Order.id == order.id)
    )
    return result.scalar_one()


@router.post(
    "/customer-return-by-admin",
    status_code=status.HTTP_201_CREATED,
    summary="Оформить возврат от клиента (Кладовщик)",
)
async def customer_return_by_admin(
    body: WarehouseDispatchCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    from app.models.enums import UserRole
    _ensure_roles(current_user, {UserRole.WAREHOUSE, UserRole.OWNER, UserRole.ADMIN})

    from app.services.store_service import StoreService
    from app.services.transaction_service import TransactionService
    from app.models.product import Product

    if not body.items:
        raise HTTPException(status_code=400, detail="No items provided")

    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="Main warehouse not found")

    txn_svc = TransactionService(session)
    product_names = []
    
    try:
        for item in body.items:
            product = await session.get(Product, item.product_id)
            if not product:
                raise ValueError(f"Товар ID {item.product_id} не найден.")
                
            await txn_svc.record_customer_return_by_admin(
                store_id=body.store_id,
                admin_user_id=current_user.id,
                product_id=item.product_id,
                quantity=item.quantity,
                warehouse_store_id=warehouse_id,
            )
            product_names.append(f"{product.sku} - {item.quantity} шт")
            
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

    # Notify sellers
    try:
        from app.bot.bot import bot
        from app.services.notification_service import NotificationService
        notif_svc = NotificationService(bot, session)
        msg_text = lambda _t: _t("return_by_admin_notif", items="\\n".join(product_names))
        await notif_svc.notify_sellers(store_id=body.store_id, text=msg_text)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to send notif: {e}")

    return {"detail": "Returns recorded successfully"}

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
    _ensure_roles(current_user, {UserRole.SELLER, UserRole.OWNER, UserRole.ADMIN, UserRole.WAREHOUSE})
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


@router.put(
    "/{order_id}/sell",
    response_model=OrderOut,
    summary="Продать доставленный заказ (Администратор)",
)
async def sell_order(
    order_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    from app.models.enums import UserRole, OrderStatus
    _ensure_roles(current_user, {UserRole.OWNER, UserRole.ADMIN, UserRole.WAREHOUSE})
    
    order_check = await session.get(Order, order_id)
    if order_check is None:
        raise HTTPException(status_code=404, detail="Order not found")
        
    _ensure_order_access(current_user, order_check)
    
    if order_check.status != OrderStatus.DELIVERED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Заказ должен быть в статусе DELIVERED для продажи. Текущий статус: {order_check.status}"
        )
        
    from app.services.transaction_service import TransactionService
    txn_svc = TransactionService(session)
    try:
        await txn_svc.record_sale(
            store_id=order_check.store_id,
            user_id=current_user.id,
            product_id=order_check.product_id,
            quantity=order_check.quantity,
            price_per_unit=order_check.price_per_item,
            order_id=order_check.id,
        )
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
        
    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id == order_id)
    )
    return result.scalar_one()


@router.put(
    "/{order_id}/return_delivered",
    response_model=OrderOut,
    summary="Возврат доставленного заказа на склад (Администратор)",
)
async def return_delivered_order(
    order_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> OrderOut:
    from app.models.enums import UserRole, OrderStatus
    _ensure_roles(current_user, {UserRole.OWNER, UserRole.ADMIN, UserRole.WAREHOUSE})
    
    order = await session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
        
    _ensure_order_access(current_user, order)
    
    if order.status != OrderStatus.DELIVERED:
        raise HTTPException(
            status_code=400,
            detail=f"Заказ должен быть в статусе DELIVERED. Текущий статус: {order.status}"
        )
        
    from app.services.store_service import StoreService
    from app.services.transaction_service import TransactionService
    from app.models.enums import StockMovementType, DebtLedgerReason
    
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="Main warehouse not found")
        
    txn_svc = TransactionService(session)
    try:
        store_inv = await txn_svc._get_inventory(order.store_id, order.product_id, lock=True)
        if store_inv is None or store_inv.quantity < order.quantity:
            available = store_inv.quantity if store_inv else 0
            raise ValueError(f"Недостаточно товара в магазине: в наличии {available}, нужно {order.quantity}.")
        store_inv.quantity -= order.quantity
        
        warehouse_inv = await txn_svc._get_or_create_inventory(warehouse_id, order.product_id, lock=True)
        warehouse_inv.quantity += order.quantity
        
        order.status = OrderStatus.RETURNED
        
        await txn_svc.record_stock_movement(
            product_id=order.product_id,
            quantity=order.quantity,
            movement_type=StockMovementType.RETURN_TO_WAREHOUSE,
            from_store_id=order.store_id,
            to_store_id=warehouse_id,
            user_id=current_user.id,
        )
        
        amount = order.price_per_item * order.quantity
        if amount > 0:
            from app.models.product import Product
            product = await session.get(Product, order.product_id)
            sku = product.sku if product else f"ID {order.product_id}"
            await txn_svc.record_debt_ledger(
                store_id=order.store_id,
                amount_change=-amount,
                reason=DebtLedgerReason.RETURN_APPROVED,
                description=f"Возврат доставленного товара #{order.id} на склад (SKU: {sku}, {order.quantity} шт.)"
            )
                
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
        
    result = await session.execute(
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.id == order_id)
    )
    return result.scalar_one()

