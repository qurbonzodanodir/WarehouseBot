import pytest
import pytest_asyncio
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

from app.core.database import Base
import app.models  # registers all models on Base.metadata

from app.models.enums import UserRole, OrderStatus, StockMovementType
from app.models.product import Product
from app.models.store import Store
from app.models.user import User
from app.models.order import Order
from app.models.inventory import Inventory
from app.models.display_inventory import DisplayInventory
from web.backend.routers.orders import deliver_order, sell_order, return_delivered_order


@pytest_asyncio.fixture(autouse=True, scope="function", loop_scope="function")
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def get_or_create_test_entities(session: AsyncSession):
    # 1. Main Warehouse
    res_wh = await session.execute(select(Store).where(Store.store_type == "warehouse"))
    wh = res_wh.scalar_one_or_none()
    if not wh:
        wh = Store(name="Main Warehouse Test", address="Warehouse Address", store_type="warehouse", current_debt=Decimal("0"))
        session.add(wh)
        await session.flush()

    # 2. Store
    res_store = await session.execute(select(Store).where(Store.name == "Test Web Action Store"))
    store = res_store.scalar_one_or_none()
    if not store:
        store = Store(name="Test Web Action Store", address="Test Address", store_type="store", current_debt=Decimal("0"))
        session.add(store)
        await session.flush()

    # 3. Product
    res_product = await session.execute(select(Product).where(Product.sku == "TEST-ACTION-SKU"))
    product = res_product.scalar_one_or_none()
    if not product:
        product = Product(sku="TEST-ACTION-SKU", brand="TEST", price=Decimal("100"), store_price=Decimal("150"), is_active=True)
        session.add(product)
        await session.flush()

    # 4. Users (Owner, Seller, Warehouse)
    users = {}
    for role in [UserRole.OWNER, UserRole.SELLER, UserRole.WAREHOUSE]:
        email = f"test_{role}@example.com"
        res_user = await session.execute(select(User).where(User.email == email))
        user = res_user.scalar_one_or_none()
        if not user:
            user = User(email=email, name=f"Test {role}", role=role, is_active=True, store_id=store.id if role == UserRole.SELLER else None)
            session.add(user)
            await session.flush()
        users[role] = user

    return store, product, users


@pytest.mark.asyncio
async def test_deliver_order_regular_success():
    async with async_session_factory() as session:
        store, product, users = await get_or_create_test_entities(session)
        
        # Create a dispatched order
        order = Order(
            store_id=store.id,
            product_id=product.id,
            quantity=3,
            price_per_item=product.price,
            total_price=product.price * 3,
            status=OrderStatus.DISPATCHED
        )
        session.add(order)
        await session.flush()
        
        # Seller receives it
        res = await deliver_order(order_id=order.id, session=session, current_user=users[UserRole.SELLER])
        assert res.status == OrderStatus.DELIVERED
        
        # Check inventory is added
        res_inv = await session.execute(
            select(Inventory).where(Inventory.store_id == store.id, Inventory.product_id == product.id)
        )
        inv = res_inv.scalar_one()
        assert inv.quantity >= 3


@pytest.mark.asyncio
async def test_deliver_order_display_fails():
    async with async_session_factory() as session:
        store, product, users = await get_or_create_test_entities(session)
        
        # Create a display_dispatched order
        order = Order(
            store_id=store.id,
            product_id=product.id,
            quantity=1,
            price_per_item=Decimal("0"),
            total_price=Decimal("0"),
            status=OrderStatus.DISPLAY_DISPATCHED
        )
        session.add(order)
        await session.flush()
        
        # Try to deliver display order — should fail with 400 bad request
        with pytest.raises(HTTPException) as exc_info:
            await deliver_order(order_id=order.id, session=session, current_user=users[UserRole.WAREHOUSE])
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_sell_order_success():
    async with async_session_factory() as session:
        store, product, users = await get_or_create_test_entities(session)
        
        # Create delivered order
        order = Order(
            store_id=store.id,
            product_id=product.id,
            quantity=2,
            price_per_item=product.price,
            total_price=product.price * 2,
            status=OrderStatus.DELIVERED
        )
        session.add(order)
        
        # Setup store inventory to have enough stock
        res_inv = await session.execute(
            select(Inventory).where(Inventory.store_id == store.id, Inventory.product_id == product.id)
        )
        inv = res_inv.scalar_one_or_none()
        if not inv:
            inv = Inventory(store_id=store.id, product_id=product.id, quantity=5)
            session.add(inv)
        else:
            inv.quantity = 5
        await session.flush()
        
        # Sell the order
        res = await sell_order(order_id=order.id, session=session, current_user=users[UserRole.OWNER])
        assert res.status == OrderStatus.SOLD
        
        # Inventory should decrease by 2
        await session.refresh(inv)
        assert inv.quantity == 3


@pytest.mark.asyncio
async def test_return_delivered_regular_success():
    async with async_session_factory() as session:
        store, product, users = await get_or_create_test_entities(session)
        
        # Create delivered order
        order = Order(
            store_id=store.id,
            product_id=product.id,
            quantity=2,
            price_per_item=product.price,
            total_price=product.price * 2,
            status=OrderStatus.DELIVERED
        )
        session.add(order)
        
        # Setup store inventory to have enough stock
        res_inv = await session.execute(
            select(Inventory).where(Inventory.store_id == store.id, Inventory.product_id == product.id)
        )
        inv = res_inv.scalar_one_or_none()
        if not inv:
            inv = Inventory(store_id=store.id, product_id=product.id, quantity=2)
            session.add(inv)
        else:
            inv.quantity = 2
            
        # Setup initial store debt
        store.current_debt = Decimal("200")
        await session.flush()
        
        # Perform return
        res = await return_delivered_order(order_id=order.id, session=session, current_user=users[UserRole.OWNER])
        assert res.status == OrderStatus.RETURNED
        
        # Store inventory should be 0, store debt should be reduced by 2 * 100 = 200 (so current_debt = 0)
        await session.refresh(inv)
        await session.refresh(store)
        assert inv.quantity == 0
        assert store.current_debt == Decimal("0")


@pytest.mark.asyncio
async def test_return_delivered_display_fails():
    async with async_session_factory() as session:
        store, product, users = await get_or_create_test_entities(session)
        
        # Create display delivered order
        order = Order(
            store_id=store.id,
            product_id=product.id,
            quantity=1,
            price_per_item=Decimal("0"),
            total_price=Decimal("0"),
            status=OrderStatus.DISPLAY_DELIVERED
        )
        session.add(order)
        await session.flush()
        
        # Perform return — should fail with 400 Bad Request
        with pytest.raises(HTTPException) as exc_info:
            await return_delivered_order(order_id=order.id, session=session, current_user=users[UserRole.OWNER])
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_unauthorized_role_raises_403():
    async with async_session_factory() as session:
        store, product, users = await get_or_create_test_entities(session)
        
        # Create delivered order
        order = Order(
            store_id=store.id,
            product_id=product.id,
            quantity=2,
            price_per_item=product.price,
            total_price=product.price * 2,
            status=OrderStatus.DELIVERED
        )
        session.add(order)
        await session.flush()
        
        # Seller should NOT be allowed to sell
        with pytest.raises(HTTPException) as exc_info:
            await sell_order(order_id=order.id, session=session, current_user=users[UserRole.SELLER])
        assert exc_info.value.status_code == 403
        
        # Seller should NOT be allowed to return delivered
        with pytest.raises(HTTPException) as exc_info:
            await return_delivered_order(order_id=order.id, session=session, current_user=users[UserRole.SELLER])
        assert exc_info.value.status_code == 403
