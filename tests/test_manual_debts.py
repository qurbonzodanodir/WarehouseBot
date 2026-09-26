from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 - register all tables
from app.core.database import Base
from app.models.enums import StoreType, UserRole
from app.models.manual_debt_transaction import ManualDebtTransaction
from app.models.store import Store
from app.models.user import User
from web.backend.routers.manual_debts import (
    create_charge,
    create_payment,
    delete_transaction,
    get_manual_debt_store,
    get_manual_debts,
    update_transaction,
)
from web.backend.schemas.manual_debts import ManualDebtCreate, ManualDebtUpdate


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def manual_debt_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def seed(session: AsyncSession):
    store = Store(
        name="Manual Debt Store",
        address="Dushanbe",
        store_type=StoreType.STORE,
        current_debt=Decimal("777.00"),
        is_active=True,
    )
    warehouse = Store(
        name="Warehouse",
        address="Dushanbe",
        store_type=StoreType.WAREHOUSE,
        current_debt=Decimal("0.00"),
        is_active=True,
    )
    owner = User(
        email="manual-debt-owner@example.com",
        name="Owner",
        role=UserRole.OWNER,
        is_active=True,
    )
    session.add_all([store, warehouse, owner])
    await session.commit()
    return store, warehouse, owner


def payload(store_id: int, amount: str, comment: str = "Комментарий"):
    return ManualDebtCreate(
        store_id=store_id,
        amount=Decimal(amount),
        operation_date=date(2026, 9, 26),
        comment=comment,
    )


@pytest.mark.asyncio
async def test_manual_debt_is_independent_from_operational_store_debt():
    async with Session() as session:
        store, _, owner = await seed(session)
        created = await create_charge(payload(store.id, "250.00"), session, owner)

        detail = await get_manual_debt_store(store.id, session, owner)
        await session.refresh(store)

        assert created.amount == Decimal("250.00")
        assert detail.balance == Decimal("250.00")
        assert store.current_debt == Decimal("777.00")


@pytest.mark.asyncio
async def test_payment_reduces_balance_and_overpayment_is_rejected():
    async with Session() as session:
        store, _, owner = await seed(session)
        await create_charge(payload(store.id, "250.00"), session, owner)
        await create_payment(payload(store.id, "90.00"), session, owner)

        detail = await get_manual_debt_store(store.id, session, owner)
        assert detail.balance == Decimal("160.00")

        with pytest.raises(HTTPException) as exc:
            await create_payment(payload(store.id, "160.01"), session, owner)
        assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_update_and_delete_keep_balance_consistent():
    async with Session() as session:
        store, _, owner = await seed(session)
        charge = await create_charge(payload(store.id, "300.00"), session, owner)
        payment = await create_payment(payload(store.id, "100.00"), session, owner)

        updated = await update_transaction(
            payment.id,
            ManualDebtUpdate(amount=Decimal("80.00"), comment="Исправлено"),
            session,
            owner,
        )
        assert updated.comment == "Исправлено"
        assert (await get_manual_debt_store(store.id, session, owner)).balance == Decimal("220.00")

        with pytest.raises(HTTPException) as exc:
            await update_transaction(
                charge.id,
                ManualDebtUpdate(amount=Decimal("50.00")),
                session,
                owner,
            )
        assert exc.value.status_code == 409

        with pytest.raises(HTTPException) as exc:
            await delete_transaction(charge.id, session, owner)
        assert exc.value.status_code == 409

        await delete_transaction(payment.id, session, owner)
        assert (await get_manual_debt_store(store.id, session, owner)).balance == Decimal("300.00")


@pytest.mark.asyncio
async def test_summary_and_store_validation():
    async with Session() as session:
        store, warehouse, owner = await seed(session)
        await create_charge(payload(store.id, "125.50"), session, owner)

        overview = await get_manual_debts(session, owner)
        assert overview.stores_with_debt == 1
        assert overview.total_debt == Decimal("125.50")
        assert [item.store_id for item in overview.stores] == [store.id]

        with pytest.raises(HTTPException) as exc:
            await create_charge(payload(warehouse.id, "20.00"), session, owner)
        assert exc.value.status_code == 404

        rows = (await session.execute(select(ManualDebtTransaction))).scalars().all()
        assert len(rows) == 1
