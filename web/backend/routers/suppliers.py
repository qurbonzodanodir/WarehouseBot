from decimal import Decimal
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func

from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.supplier_invoice_item import SupplierInvoiceLineItem
from app.models.supplier_payment import SupplierPayment
from app.models.product import Product
from app.models.enums import UserRole
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.suppliers import (
    SupplierCreate,
    SupplierOut,
    SupplierInvoiceCreate,
    SupplierInvoiceOut,
    SupplierInvoiceLineItemOut,
    SupplierPaymentCreate,
    SupplierPaymentOut,
    SupplierDetailOut,
)

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

_ALLOWED_ROLES = (UserRole.OWNER, UserRole.ADMIN, UserRole.WAREHOUSE)


async def _get_supplier_debt(session, supplier_id: int) -> tuple[Decimal, Decimal, Decimal]:
    """Returns (total_invoiced, total_paid, current_debt)."""
    inv_res = await session.execute(
        select(func.coalesce(func.sum(SupplierInvoice.total_amount), 0))
        .where(SupplierInvoice.supplier_id == supplier_id)
    )
    total_invoiced = inv_res.scalar() or Decimal(0)

    pay_res = await session.execute(
        select(func.coalesce(func.sum(SupplierPayment.amount), 0))
        .where(SupplierPayment.supplier_id == supplier_id)
    )
    total_paid = pay_res.scalar() or Decimal(0)

    return Decimal(total_invoiced), Decimal(total_paid), Decimal(total_invoiced) - Decimal(total_paid)


@router.get("", response_model=list[SupplierOut], summary="Список поставщиков с текущим долгом")
async def list_suppliers(session: SessionDep, current_user: CurrentUser) -> list[SupplierOut]:
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await session.execute(select(Supplier).where(Supplier.is_active.is_(True)).order_by(Supplier.name))
    suppliers = result.scalars().all()

    out = []
    for s in suppliers:
        _, _, debt = await _get_supplier_debt(session, s.id)
        out.append(SupplierOut(
            id=s.id, name=s.name, contact_info=s.contact_info,
            address=s.address, notes=s.notes, is_active=s.is_active,
            created_at=s.created_at, current_debt=debt,
        ))
    return out


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED, summary="Создать поставщика")
async def create_supplier(body: SupplierCreate, session: SessionDep, current_user: CurrentUser) -> SupplierOut:
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")

    supplier = Supplier(
        name=body.name,
        contact_info=body.contact_info,
        address=body.address,
        notes=body.notes,
    )
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)

    return SupplierOut(
        id=supplier.id, name=supplier.name, contact_info=supplier.contact_info,
        address=supplier.address, notes=supplier.notes, is_active=supplier.is_active,
        created_at=supplier.created_at, current_debt=Decimal(0),
    )


@router.get("/{supplier_id}", response_model=SupplierDetailOut, summary="Детали поставщика + история")
async def get_supplier(supplier_id: int, session: SessionDep, current_user: CurrentUser) -> SupplierDetailOut:
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")

    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    total_invoiced, total_paid, current_debt = await _get_supplier_debt(session, supplier_id)

    from sqlalchemy.orm import selectinload
    # Invoices with user names and items
    inv_result = await session.execute(
        select(SupplierInvoice).where(SupplierInvoice.supplier_id == supplier_id)
        .options(selectinload(SupplierInvoice.items))
        .order_by(SupplierInvoice.created_at.desc())
    )
    invoices_raw = inv_result.scalars().all()

    # Payments with user names
    pay_result = await session.execute(
        select(SupplierPayment).where(SupplierPayment.supplier_id == supplier_id)
        .order_by(SupplierPayment.created_at.desc())
    )
    payments_raw = pay_result.scalars().all()

    from app.models.user import User

    async def get_user_name(user_id: int) -> str | None:
        u = await session.get(User, user_id)
        return u.name if u else None

    invoices = []
    for inv in invoices_raw:
        invoices.append(SupplierInvoiceOut(
            id=inv.id, supplier_id=inv.supplier_id, total_amount=inv.total_amount,
            notes=inv.notes, created_at=inv.created_at,
            items=[
                SupplierInvoiceLineItemOut(
                    product_id=it.product_id, sku="", quantity=it.quantity, price_per_unit=it.price_per_unit, line_total=it.quantity * it.price_per_unit
                ) for it in inv.items
            ],
            user_name=await get_user_name(inv.user_id)
        ))

    payments = []
    for pay in payments_raw:
        payments.append(SupplierPaymentOut(
            id=pay.id, supplier_id=pay.supplier_id, amount=pay.amount,
            notes=pay.notes, created_at=pay.created_at,
            user_name=await get_user_name(pay.user_id)
        ))

    return SupplierDetailOut(
        id=supplier.id, name=supplier.name, contact_info=supplier.contact_info,
        address=supplier.address, notes=supplier.notes, is_active=supplier.is_active,
        created_at=supplier.created_at, current_debt=current_debt,
        total_invoiced=total_invoiced, total_paid=total_paid,
        invoices=invoices, payments=payments,
    )


@router.post("/{supplier_id}/invoices", response_model=SupplierInvoiceOut, status_code=status.HTTP_201_CREATED, summary="Отгрузить товары оптовику (записывает долг)")
async def add_invoice(supplier_id: int, body: SupplierInvoiceCreate, session: SessionDep, current_user: CurrentUser) -> SupplierInvoiceOut:
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")

    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Load all requested products at once
    product_ids = [item.product_id for item in body.items]
    products_result = await session.execute(
        select(Product).where(Product.id.in_(product_ids))
    )
    products_map: dict[int, Product] = {p.id: p for p in products_result.scalars().all()}

    # Validate all products exist
    for item in body.items:
        if item.product_id not in products_map:
            raise HTTPException(status_code=404, detail=f"Product with id={item.product_id} not found")

    # Find warehouse store_id
    from app.services.store_service import StoreService
    from app.services.transaction_service import TransactionService

    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=404, detail="Главный склад не найден")

    # Calculate total from product prices × quantities
    total_amount = sum(
        products_map[item.product_id].price * item.quantity
        for item in body.items
    )

    try:
        # Create invoice
        invoice = SupplierInvoice(
            supplier_id=supplier_id,
            user_id=current_user.id,
            total_amount=Decimal(str(total_amount)),
            notes=body.notes,
        )
        session.add(invoice)
        await session.flush()  # Get invoice.id

        txn_svc = TransactionService(session)

        # Deduct inventory and create line items
        line_items_out = []
        for item in body.items:
            product = products_map[item.product_id]

            # Deduct from warehouse (raises ValueError if insufficient stock)
            await txn_svc.dispatch_to_wholesaler(
                warehouse_store_id=warehouse_id,
                product_id=product.id,
                quantity=item.quantity,
                user_id=current_user.id,
            )

            line = SupplierInvoiceLineItem(
                invoice_id=invoice.id,
                product_id=product.id,
                quantity=item.quantity,
                price_per_unit=product.price,
            )
            session.add(line)
            line_items_out.append(SupplierInvoiceLineItemOut(
                product_id=product.id,
                sku=product.sku,
                quantity=item.quantity,
                price_per_unit=product.price,
                line_total=product.price * item.quantity,
            ))

        await session.commit()

    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await session.rollback()
        raise

    return SupplierInvoiceOut(
        id=invoice.id, supplier_id=invoice.supplier_id, total_amount=invoice.total_amount,
        notes=invoice.notes, created_at=invoice.created_at, user_name=current_user.name,
        items=line_items_out,
    )



@router.post("/{supplier_id}/payments", response_model=SupplierPaymentOut, status_code=status.HTTP_201_CREATED, summary="Провести оплату поставщику (долг уменьшается)")
async def add_payment(supplier_id: int, body: SupplierPaymentCreate, session: SessionDep, current_user: CurrentUser) -> SupplierPaymentOut:
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")

    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Check: don't allow overpayment
    _, _, current_debt = await _get_supplier_debt(session, supplier_id)
    if body.amount > current_debt:
        raise HTTPException(status_code=400, detail=f"Payment amount ({body.amount}) exceeds current debt ({current_debt})")

    payment = SupplierPayment(
        supplier_id=supplier_id,
        user_id=current_user.id,
        amount=body.amount,
        notes=body.notes,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    return SupplierPaymentOut(
        id=payment.id, supplier_id=payment.supplier_id, amount=payment.amount,
        notes=payment.notes, created_at=payment.created_at, user_name=current_user.name,
    )
