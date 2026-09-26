from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 - register all models
from app.core.database import Base
from app.models.enums import StoreType, UserRole
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.store import Store
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.supplier_invoice_item import SupplierInvoiceLineItem
from app.models.supplier_outgoing_return import SupplierOutgoingReturn
from app.models.supplier_outgoing_return_item import SupplierOutgoingReturnLineItem
from app.models.supplier_receipt import SupplierReceipt
from app.models.supplier_receipt_item import SupplierReceiptLineItem
from app.models.supplier_return import SupplierReturn
from app.models.supplier_return_item import SupplierReturnLineItem
from app.models.user import User
from app.models.supplier_payment import SupplierPayment
from app.models.supplier_payout import SupplierPayout
from web.backend.routers.suppliers import (
    _get_supplier_debt,
    delete_invoice,
    delete_outgoing_return,
    delete_payment,
    delete_payout,
    delete_receipt,
    delete_return,
    patch_invoice,
    patch_outgoing_return,
    patch_payment,
    patch_payout,
    patch_receipt,
    patch_return,
)
from web.backend.schemas.suppliers import (
    SupplierInvoiceUpdate,
    SupplierOutgoingReturnUpdate,
    SupplierPaymentUpdate,
    SupplierPayoutUpdate,
    SupplierReceiptUpdate,
    SupplierReturnUpdate,
)


engine = create_async_engine("sqlite+aiosqlite:///:memory:")
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def make_entities(session: AsyncSession, inventory_quantity: int):
    warehouse = Store(
        name="Test warehouse",
        address="",
        store_type=StoreType.WAREHOUSE,
        current_debt=Decimal("0"),
    )
    owner = User(
        email="supplier-test@example.com",
        name="Test owner",
        role=UserRole.OWNER,
        is_active=True,
    )
    supplier = Supplier(name="Test partner")
    product = Product(
        sku="SUP-TEST",
        brand="Test",
        price=Decimal("100"),
        store_price=Decimal("100"),
        is_active=True,
    )
    session.add_all([warehouse, owner, supplier, product])
    await session.flush()
    inventory = Inventory(
        store_id=warehouse.id,
        product_id=product.id,
        quantity=inventory_quantity,
    )
    session.add(inventory)
    await session.flush()
    return warehouse, owner, supplier, product, inventory


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation_model", "line_model", "delete_operation", "initial_quantity", "expected_quantity"),
    [
        (SupplierInvoice, SupplierInvoiceLineItem, delete_invoice, 7, 10),
        (SupplierReturn, SupplierReturnLineItem, delete_return, 13, 10),
        (SupplierReceipt, SupplierReceiptLineItem, delete_receipt, 13, 10),
        (
            SupplierOutgoingReturn,
            SupplierOutgoingReturnLineItem,
            delete_outgoing_return,
            7,
            10,
        ),
    ],
)
async def test_delete_goods_operation_reverses_inventory_and_debt(
    operation_model,
    line_model,
    delete_operation,
    initial_quantity,
    expected_quantity,
):
    async with session_factory() as session:
        _, owner, supplier, product, inventory = await make_entities(
            session, initial_quantity
        )
        operation = operation_model(
            supplier_id=supplier.id,
            user_id=owner.id,
            total_amount=Decimal("300"),
        )
        session.add(operation)
        await session.flush()
        parent_field = {
            SupplierInvoiceLineItem: "invoice_id",
            SupplierReturnLineItem: "return_id",
            SupplierReceiptLineItem: "receipt_id",
            SupplierOutgoingReturnLineItem: "return_id",
        }[line_model]
        session.add(
            line_model(
                **{parent_field: operation.id},
                product_id=product.id,
                quantity=3,
                price_per_unit=Decimal("100"),
            )
        )
        await session.commit()

        await delete_operation(supplier.id, operation.id, session, owner)

        await session.refresh(inventory)
        assert inventory.quantity == expected_quantity
        assert await session.get(operation_model, operation.id) is None
        debt = await _get_supplier_debt(session, supplier.id)
        assert debt[3] == Decimal("0")
        assert debt[7] == Decimal("0")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation_model", "line_model", "delete_operation"),
    [
        (SupplierReturn, SupplierReturnLineItem, delete_return),
        (SupplierReceipt, SupplierReceiptLineItem, delete_receipt),
    ],
)
async def test_delete_received_goods_is_blocked_when_stock_was_already_used(
    operation_model, line_model, delete_operation
):
    async with session_factory() as session:
        _, owner, supplier, product, inventory = await make_entities(session, 2)
        operation = operation_model(
            supplier_id=supplier.id,
            user_id=owner.id,
            total_amount=Decimal("300"),
        )
        session.add(operation)
        await session.flush()
        parent_field = (
            "receipt_id" if line_model is SupplierReceiptLineItem else "return_id"
        )
        session.add(
            line_model(
                **{parent_field: operation.id},
                product_id=product.id,
                quantity=3,
                price_per_unit=Decimal("100"),
            )
        )
        await session.commit()
        operation_id = operation.id

        with pytest.raises(HTTPException) as error:
            await delete_operation(supplier.id, operation_id, session, owner)

        assert error.value.status_code == 409
        await session.refresh(inventory)
        assert inventory.quantity == 2
        assert await session.get(operation_model, operation_id) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation_model", "line_model", "patch_operation", "update_model"),
    [
        (SupplierInvoice, SupplierInvoiceLineItem, patch_invoice, SupplierInvoiceUpdate),
        (SupplierReturn, SupplierReturnLineItem, patch_return, SupplierReturnUpdate),
        (SupplierReceipt, SupplierReceiptLineItem, patch_receipt, SupplierReceiptUpdate),
        (
            SupplierOutgoingReturn,
            SupplierOutgoingReturnLineItem,
            patch_outgoing_return,
            SupplierOutgoingReturnUpdate,
        ),
    ],
)
async def test_patch_goods_operation_updates_note_and_date(
    operation_model, line_model, patch_operation, update_model
):
    async with session_factory() as session:
        _, owner, supplier, product, _ = await make_entities(session, 10)
        operation = operation_model(
            supplier_id=supplier.id,
            user_id=owner.id,
            total_amount=Decimal("300"),
            notes="old",
        )
        session.add(operation)
        await session.flush()
        parent_field = {
            SupplierInvoiceLineItem: "invoice_id",
            SupplierReturnLineItem: "return_id",
            SupplierReceiptLineItem: "receipt_id",
            SupplierOutgoingReturnLineItem: "return_id",
        }[line_model]
        session.add(
            line_model(
                **{parent_field: operation.id},
                product_id=product.id,
                quantity=3,
                price_per_unit=Decimal("100"),
            )
        )
        await session.commit()

        result = await patch_operation(
            supplier.id,
            operation.id,
            update_model(notes="updated", operation_date=date(2026, 9, 20)),
            session,
            owner,
        )

        assert result.notes == "updated"
        assert result.created_at.date() == date(2026, 9, 20)
        assert len(result.items) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "balance_record_model",
        "money_record_model",
        "patch_operation",
        "delete_operation",
        "update_model",
        "balance_index",
    ),
    [
        (
            SupplierInvoice,
            SupplierPayment,
            patch_payment,
            delete_payment,
            SupplierPaymentUpdate,
            3,
        ),
        (
            SupplierReceipt,
            SupplierPayout,
            patch_payout,
            delete_payout,
            SupplierPayoutUpdate,
            7,
        ),
    ],
)
async def test_patch_and_delete_money_operation_recalculates_balance(
    balance_record_model,
    money_record_model,
    patch_operation,
    delete_operation,
    update_model,
    balance_index,
):
    async with session_factory() as session:
        _, owner, supplier, _, _ = await make_entities(session, 10)
        balance_record = balance_record_model(
            supplier_id=supplier.id,
            user_id=owner.id,
            total_amount=Decimal("100"),
        )
        money_record = money_record_model(
            supplier_id=supplier.id,
            user_id=owner.id,
            amount=Decimal("20"),
            notes="old",
        )
        session.add_all([balance_record, money_record])
        await session.commit()

        result = await patch_operation(
            supplier.id,
            money_record.id,
            update_model(
                amount=Decimal("35"),
                notes="updated",
                operation_date=date(2026, 9, 20),
            ),
            session,
            owner,
        )
        assert result.amount == Decimal("35")
        assert result.notes == "updated"
        assert result.created_at.date() == date(2026, 9, 20)
        assert (await _get_supplier_debt(session, supplier.id))[balance_index] == Decimal(
            "65"
        )

        await delete_operation(supplier.id, money_record.id, session, owner)
        assert (await _get_supplier_debt(session, supplier.id))[balance_index] == Decimal(
            "100"
        )
