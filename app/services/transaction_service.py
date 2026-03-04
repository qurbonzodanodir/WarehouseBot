from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.enums import TransactionType
from app.models.inventory import Inventory
from app.models.store import Store
from app.models.transaction import Transaction


async def record_sale(
    session: AsyncSession,
    store_id: int,
    user_id: int,
    product_id: int,
    quantity: int,
    price_per_unit: Decimal,
    order_id: int = None,
) -> Transaction:

    # Check inventory
    inv = await _get_inventory(session, store_id, product_id)
    if inv is None or inv.quantity < quantity:
        available = inv.quantity if inv else 0
        raise ValueError(
            f"Insufficient stock: have {available}, need {quantity}."
        )

    if order_id is not None:
        from app.models.order import Order
        from app.models.enums import OrderStatus
        order = await session.get(Order, order_id)
        if order:
            if order.status != OrderStatus.DELIVERED:
                raise ValueError("Заявка уже обработана (продана или возвращена).")
            order.status = OrderStatus.SOLD

    amount = price_per_unit * quantity

    # Deduct inventory
    inv.quantity -= quantity

    # Record transaction
    txn = Transaction(
        store_id=store_id,
        user_id=user_id,
        type=TransactionType.SALE,
        amount=amount,
        product_id=product_id,
        quantity=quantity,
    )
    session.add(txn)

    # Increase debt
    store = await session.get(Store, store_id)
    store.current_debt += amount

    await session.flush()
    return txn


async def initiate_return(
    session: AsyncSession,
    store_id: int,
    user_id: int,
    product_id: int,
    quantity: int,
    order_id: int,
) -> None:
    """
    Step 1: Seller initiates a return.
    - Locks/deducts quantity from the store inventory.
    - Sets order status to RETURN_PENDING.
    - Does NOT decrease debt yet.
    """
    inv = await _get_inventory(session, store_id, product_id)
    if inv is None or inv.quantity < quantity:
        available = inv.quantity if inv else 0
        raise ValueError(f"Insufficient stock to return: have {available}, need {quantity}.")

    inv.quantity -= quantity

    from app.models.order import Order
    from app.models.enums import OrderStatus
    order = await session.get(Order, order_id)
    if order:
        if order.status not in (OrderStatus.DELIVERED, OrderStatus.RETURN_PENDING):
            raise ValueError(f"Заявка #{order_id} имеет статус {order.status}, возврат невозможен.")
        order.status = OrderStatus.RETURN_PENDING

    await session.flush()


async def approve_return(
    session: AsyncSession,
    warehouse_store_id: int,
    warehouse_user_id: int,
    order_id: int,
) -> Transaction:
    """
    Step 2 (Approve): Warehouse approves the return.
    - Credit quantity back to main warehouse inventory.
    - Create RETURN transaction (negative amount).
    - Decrease store current_debt.
    - Set order status to RETURNED.
    """
    from app.models.order import Order
    from app.models.enums import OrderStatus
    from app.models.product import Product
    order = await session.get(Order, order_id)
    if order is None or order.status != OrderStatus.RETURN_PENDING:
        raise ValueError("Invalid order status for return approval.")

    product = await session.get(Product, order.product_id)
    amount = product.price * order.quantity

    # Credit inventory back to the Warehouse's store
    inv = await _get_or_create_inventory(session, warehouse_store_id, order.product_id)
    inv.quantity += order.quantity

    order.status = OrderStatus.RETURNED

    txn = Transaction(
        store_id=order.store_id, # Link transaction to the shop that originated it
        user_id=warehouse_user_id,
        type=TransactionType.RETURN,
        amount=amount,
        product_id=order.product_id,
        quantity=order.quantity,
    )
    session.add(txn)

    # Decrease debt for the Store (not warehouse)
    store = await session.get(Store, order.store_id)
    store.current_debt -= amount

    await session.flush()
    return txn


async def reject_return(
    session: AsyncSession,
    order_id: int,
) -> None:
    """
    Step 2 (Reject): Warehouse rejects the return.
    - Put stock back into the Store's inventory.
    - Set order status back to DELIVERED.
    """
    from app.models.order import Order
    from app.models.enums import OrderStatus
    order = await session.get(Order, order_id)
    if order is None or order.status != OrderStatus.RETURN_PENDING:
        raise ValueError("Invalid order status for return rejection.")

    # Put inventory back into the store
    inv = await _get_or_create_inventory(session, order.store_id, order.product_id)
    inv.quantity += order.quantity

    order.status = OrderStatus.DELIVERED
    await session.flush()


async def record_cash_collection(
    session: AsyncSession,
    store_id: int,
    admin_user_id: int,
    amount: Decimal,
) -> Transaction:
    """
    Admin collects cash from a store.
    - Create CASH_COLLECTION transaction.
    - Decrease store current_debt.
    """
    store = await session.get(Store, store_id)
    if store is None:
        raise ValueError(f"Store #{store_id} not found.")

    txn = Transaction(
        store_id=store_id,
        user_id=admin_user_id,
        type=TransactionType.CASH_COLLECTION,
        amount=amount,
    )
    session.add(txn)

    store.current_debt -= amount
    await session.flush()
    return txn


async def get_store_transactions(
    session: AsyncSession,
    store_id: int,
    limit: int = 20,
) -> list[Transaction]:
    """Get recent transactions for a store."""
    stmt = (
        select(Transaction)
        .options(joinedload(Transaction.user), joinedload(Transaction.product))
        .where(Transaction.store_id == store_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_stores_with_debt(session: AsyncSession) -> list[Store]:
    """Return all stores that have outstanding debt > 0."""
    stmt = (
        select(Store)
        .where(Store.is_active.is_(True), Store.current_debt > 0)
        .order_by(Store.current_debt.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_inventory(
    session: AsyncSession, store_id: int, product_id: int
) -> Inventory | None:
    stmt = select(Inventory).where(
        Inventory.store_id == store_id,
        Inventory.product_id == product_id,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_or_create_inventory(
    session: AsyncSession, store_id: int, product_id: int
) -> Inventory:
    inv = await _get_inventory(session, store_id, product_id)
    if inv is None:
        inv = Inventory(
            store_id=store_id, product_id=product_id, quantity=0
        )
        session.add(inv)
        await session.flush()
    return inv
