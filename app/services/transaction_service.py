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
) -> Transaction:

    # Check inventory
    inv = await _get_inventory(session, store_id, product_id)
    if inv is None or inv.quantity < quantity:
        available = inv.quantity if inv else 0
        raise ValueError(
            f"Insufficient stock: have {available}, need {quantity}."
        )

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


async def record_return(
    session: AsyncSession,
    store_id: int,
    user_id: int,
    product_id: int,
    quantity: int,
    price_per_unit: Decimal,
    reason: str,
) -> Transaction:
    """
    Record a product return.
    - Credit quantity back to store inventory.
    - Create RETURN transaction (negative amount in terms of debt).
    - Decrease store current_debt.
    """
    amount = price_per_unit * quantity

    # Credit inventory back
    inv = await _get_or_create_inventory(session, store_id, product_id)
    inv.quantity += quantity

    txn = Transaction(
        store_id=store_id,
        user_id=user_id,
        type=TransactionType.RETURN,
        amount=amount,
        product_id=product_id,
        quantity=quantity,
    )
    session.add(txn)

    # Decrease debt
    store = await session.get(Store, store_id)
    store.current_debt -= amount

    await session.flush()
    return txn


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
