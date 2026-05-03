from decimal import Decimal
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.supplier_invoice_item import SupplierInvoiceLineItem
from app.models.supplier_return import SupplierReturn
from app.models.supplier_return_item import SupplierReturnLineItem
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
    SupplierReturnCreate,
    SupplierReturnOut,
    SupplierReturnLineItemOut,
)

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

_ALLOWED_ROLES = (UserRole.OWNER, UserRole.ADMIN, UserRole.WAREHOUSE)


async def _get_supplier_debt(session, supplier_id: int) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Returns (total_invoiced, total_paid, total_returned, current_debt)."""
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

    ret_res = await session.execute(
        select(func.coalesce(func.sum(SupplierReturn.total_amount), 0))
        .where(SupplierReturn.supplier_id == supplier_id)
    )
    total_returned = ret_res.scalar() or Decimal(0)

    total_invoiced = Decimal(total_invoiced)
    total_paid = Decimal(total_paid)
    total_returned = Decimal(total_returned)
    
    current_debt = total_invoiced - total_paid - total_returned
    return total_invoiced, total_paid, total_returned, current_debt


def _supplier_debt_subqueries():
    invoiced_subq = (
        select(
            SupplierInvoice.supplier_id.label("supplier_id"),
            func.coalesce(func.sum(SupplierInvoice.total_amount), 0).label("total_invoiced"),
        )
        .group_by(SupplierInvoice.supplier_id)
        .subquery()
    )
    paid_subq = (
        select(
            SupplierPayment.supplier_id.label("supplier_id"),
            func.coalesce(func.sum(SupplierPayment.amount), 0).label("total_paid"),
        )
        .group_by(SupplierPayment.supplier_id)
        .subquery()
    )
    returned_subq = (
        select(
            SupplierReturn.supplier_id.label("supplier_id"),
            func.coalesce(func.sum(SupplierReturn.total_amount), 0).label("total_returned"),
        )
        .group_by(SupplierReturn.supplier_id)
        .subquery()
    )
    return invoiced_subq, paid_subq, returned_subq


@router.get("", response_model=list[SupplierOut], summary="Список поставщиков с текущим долгом")
async def list_suppliers(session: SessionDep, current_user: CurrentUser) -> list[SupplierOut]:
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")

    invoiced_subq, paid_subq, returned_subq = _supplier_debt_subqueries()
    result = await session.execute(
        select(
            Supplier,
            func.coalesce(invoiced_subq.c.total_invoiced, 0).label("total_invoiced"),
            func.coalesce(paid_subq.c.total_paid, 0).label("total_paid"),
            func.coalesce(returned_subq.c.total_returned, 0).label("total_returned"),
        )
        .outerjoin(invoiced_subq, invoiced_subq.c.supplier_id == Supplier.id)
        .outerjoin(paid_subq, paid_subq.c.supplier_id == Supplier.id)
        .outerjoin(returned_subq, returned_subq.c.supplier_id == Supplier.id)
        .where(Supplier.is_active.is_(True))
        .order_by(Supplier.name)
    )

    out = []
    for supplier, total_invoiced, total_paid, total_returned in result.all():
        current_debt = Decimal(total_invoiced) - Decimal(total_paid) - Decimal(total_returned)
        out.append(SupplierOut(
            id=supplier.id, name=supplier.name, contact_info=supplier.contact_info,
            address=supplier.address, notes=supplier.notes, is_active=supplier.is_active,
            created_at=supplier.created_at, current_debt=current_debt,
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

    total_invoiced, total_paid, total_returned, current_debt = await _get_supplier_debt(session, supplier_id)

    # Invoices with user names and items
    inv_result = await session.execute(
        select(SupplierInvoice).where(SupplierInvoice.supplier_id == supplier_id)
        .options(
            selectinload(SupplierInvoice.user),
            selectinload(SupplierInvoice.items).selectinload(SupplierInvoiceLineItem.product),
        )
        .order_by(SupplierInvoice.created_at.desc())
    )
    invoices_raw = inv_result.scalars().all()

    # Payments with user names
    pay_result = await session.execute(
        select(SupplierPayment).where(SupplierPayment.supplier_id == supplier_id)
        .options(selectinload(SupplierPayment.user))
        .order_by(SupplierPayment.created_at.desc())
    )
    payments_raw = pay_result.scalars().all()

    # Returns with items
    ret_result = await session.execute(
        select(SupplierReturn).where(SupplierReturn.supplier_id == supplier_id)
        .options(
            selectinload(SupplierReturn.user),
            selectinload(SupplierReturn.items).selectinload(SupplierReturnLineItem.product),
        )
        .order_by(SupplierReturn.created_at.desc())
    )
    returns_raw = ret_result.scalars().all()

    invoices = []
    for inv in invoices_raw:
        invoices.append(SupplierInvoiceOut(
            id=inv.id, supplier_id=inv.supplier_id, total_amount=inv.total_amount,
            notes=inv.notes, created_at=inv.created_at,
            items=[
                SupplierInvoiceLineItemOut(
                    product_id=it.product_id,
                    sku=it.product.sku if it.product else "",
                    quantity=it.quantity,
                    price_per_unit=it.price_per_unit,
                    line_total=it.quantity * it.price_per_unit,
                ) for it in inv.items
            ],
            user_name=inv.user.name if inv.user else None,
        ))

    payments = []
    for pay in payments_raw:
        payments.append(SupplierPaymentOut(
            id=pay.id, supplier_id=pay.supplier_id, amount=pay.amount,
            notes=pay.notes, created_at=pay.created_at,
            user_name=pay.user.name if pay.user else None,
        ))

    returns = []
    for ret in returns_raw:
        returns.append(SupplierReturnOut(
            id=ret.id, supplier_id=ret.supplier_id, total_amount=ret.total_amount,
            notes=ret.notes, created_at=ret.created_at,
            items=[
                SupplierReturnLineItemOut(
                    product_id=it.product_id,
                    sku=it.product.sku if it.product else "",
                    quantity=it.quantity,
                    price_per_unit=it.price_per_unit,
                    line_total=it.quantity * it.price_per_unit,
                ) for it in ret.items
            ],
            user_name=ret.user.name if ret.user else None,
        ))

    return SupplierDetailOut(
        id=supplier.id, name=supplier.name, contact_info=supplier.contact_info,
        address=supplier.address, notes=supplier.notes, is_active=supplier.is_active,
        created_at=supplier.created_at, current_debt=current_debt,
        total_invoiced=total_invoiced, total_paid=total_paid,
        total_returned=total_returned,
        invoices=invoices, payments=payments, returns=returns
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
    _, _, _, current_debt = await _get_supplier_debt(session, supplier_id)
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


@router.post("/{supplier_id}/returns", response_model=SupplierReturnOut, status_code=status.HTTP_201_CREATED, summary="Принять возврат от оптовика (уменьшает долг)")
async def add_return(supplier_id: int, body: SupplierReturnCreate, session: SessionDep, current_user: CurrentUser) -> SupplierReturnOut:
    if current_user.role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="Access denied")

    supplier = await session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    product_ids = [item.product_id for item in body.items]
    products_result = await session.execute(select(Product).where(Product.id.in_(product_ids)))
    products_map: dict[int, Product] = {p.id: p for p in products_result.scalars().all()}

    for item in body.items:
        if item.product_id not in products_map:
            raise HTTPException(status_code=404, detail=f"Product id={item.product_id} not found")

    from app.services.store_service import StoreService
    from app.services.transaction_service import TransactionService

    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=404, detail="Главный склад не найден")

    total_amount = sum(products_map[item.product_id].price * item.quantity for item in body.items)

    try:
        ret = SupplierReturn(
            supplier_id=supplier_id,
            user_id=current_user.id,
            total_amount=Decimal(str(total_amount)),
            notes=body.notes,
        )
        session.add(ret)
        await session.flush()

        txn_svc = TransactionService(session)
        line_items_out = []
        for item in body.items:
            product = products_map[item.product_id]
            
            # Increase warehouse stock
            await txn_svc.receive_from_wholesaler(
                warehouse_store_id=warehouse_id,
                product_id=product.id,
                quantity=item.quantity,
                user_id=current_user.id,
            )

            line = SupplierReturnLineItem(
                return_id=ret.id,
                product_id=product.id,
                quantity=item.quantity,
                price_per_unit=product.price,
            )
            session.add(line)
            line_items_out.append(SupplierReturnLineItemOut(
                product_id=product.id,
                sku=product.sku,
                quantity=item.quantity,
                price_per_unit=product.price,
                line_total=product.price * item.quantity,
            ))

        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return SupplierReturnOut(
        id=ret.id, supplier_id=ret.supplier_id, total_amount=ret.total_amount,
        notes=ret.notes, created_at=ret.created_at, user_name=current_user.name,
        items=line_items_out,
    )
