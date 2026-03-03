from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrderStatus
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.product import Product


async def get_available_products(session: AsyncSession) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_store_inventory(
    session: AsyncSession, store_id: int
) -> list[Inventory]:
    from sqlalchemy.orm import joinedload

    stmt = (
        select(Inventory)
        .options(joinedload(Inventory.product))
        .where(Inventory.store_id == store_id, Inventory.quantity > 0)
        .order_by(Inventory.product_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())



async def create_order(
    session: AsyncSession,
    store_id: int,
    product_id: int,
    quantity: int,
) -> Order:
    order = Order(
        store_id=store_id,
        product_id=product_id,
        quantity=quantity,
        status=OrderStatus.PENDING,
    )
    session.add(order)
    await session.flush()
    return order


async def dispatch_order(
    session: AsyncSession,
    order_id: int,
    warehouse_store_id: int,
) -> Order:

    order = await session.get(Order, order_id)
    if order is None or order.status != OrderStatus.PENDING:
        raise ValueError(f"Order #{order_id} is not in PENDING status.")

    # Deduct from warehouse inventory
    inv = await _get_or_create_inventory(
        session, warehouse_store_id, order.product_id
    )
    if inv.quantity < order.quantity:
        raise ValueError(
            f"Not enough stock: have {inv.quantity}, need {order.quantity}."
        )
    inv.quantity -= order.quantity

    order.status = OrderStatus.DISPATCHED
    await session.flush()
    return order


async def deliver_order(
    session: AsyncSession,
    order_id: int,
) -> Order:
    """
    Seller accepts delivery.
    - Add quantity to the store's inventory.
    - Set order status to DELIVERED.
    """
    order = await session.get(Order, order_id)
    if order is None or order.status != OrderStatus.DISPATCHED:
        raise ValueError(f"Order #{order_id} is not in DISPATCHED status.")

    # Credit to store inventory
    inv = await _get_or_create_inventory(
        session, order.store_id, order.product_id
    )
    inv.quantity += order.quantity

    order.status = OrderStatus.DELIVERED
    await session.flush()
    return order


async def reject_order(
    session: AsyncSession,
    order_id: int,
) -> Order:
    """Warehouse or seller rejects the order."""
    order = await session.get(Order, order_id)
    if order is None:
        raise ValueError(f"Order #{order_id} not found.")
    order.status = OrderStatus.REJECTED
    await session.flush()
    return order


async def get_pending_orders(session: AsyncSession) -> list[Order]:
    """Return all pending orders (for warehouse view)."""
    from sqlalchemy.orm import joinedload

    stmt = (
        select(Order)
        .options(joinedload(Order.store), joinedload(Order.product))
        .where(Order.status == OrderStatus.PENDING)
        .order_by(Order.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_dispatched_orders_for_store(
    session: AsyncSession, store_id: int
) -> list[Order]:
    """Return dispatched (in-transit) orders for a specific store."""
    from sqlalchemy.orm import joinedload

    stmt = (
        select(Order)
        .options(joinedload(Order.product))
        .where(
            Order.store_id == store_id,
            Order.status == OrderStatus.DISPATCHED,
        )
        .order_by(Order.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_or_create_inventory(
    session: AsyncSession,
    store_id: int,
    product_id: int,
) -> Inventory:
    """Get an inventory row or create one with quantity=0."""
    stmt = select(Inventory).where(
        Inventory.store_id == store_id,
        Inventory.product_id == product_id,
    )
    result = await session.execute(stmt)
    inv = result.scalar_one_or_none()
    if inv is None:
        inv = Inventory(
            store_id=store_id, product_id=product_id, quantity=0
        )
        session.add(inv)
        await session.flush()
    return inv
