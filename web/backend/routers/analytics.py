from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, case, func, select

from app.models.enums import OrderStatus
from app.models.enums import UserRole
from app.models.order import Order
from app.models.sale import Sale
from app.models.store import Store
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.supplier_payment import SupplierPayment
from app.models.supplier_return import SupplierReturn
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.analytics import (
    DashboardResponse,
    OrderStatusCount,
    StoreDebt,
    SupplierDebt,
    StoreRevenue,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _get_period_dates(period: str) -> tuple[datetime, datetime | None]:
    today_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    if period == "yesterday":
        return today_start - timedelta(days=1), today_start
    elif period == "week":
        return today_start - timedelta(days=7), None
    elif period == "month":
        return today_start - timedelta(days=30), None
    elif period == "year":
        return today_start - timedelta(days=365), None
    return today_start, None  # today default


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Дашборд владельца",
    description="KPI метрики: продажи, инкассации, возвраты, долги по магазинам.",
)
async def get_dashboard(
    session: SessionDep,
    current_user: CurrentUser,
    period: str = Query("today", pattern="^(today|yesterday|week|month|year)$"),
) -> DashboardResponse:
    if current_user.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Access denied")

    start_date, end_date = _get_period_dates(period)

    # ── 1. Продажи за период ──────────────────────────────────────────────────
    sales_stmt = select(
        func.count(Sale.id),
        func.coalesce(func.sum(Sale.total_amount), 0),
    ).where(Sale.created_at >= start_date)
    if end_date:
        sales_stmt = sales_stmt.where(Sale.created_at < end_date)
    sales_result = await session.execute(sales_stmt)
    orders_count, revenue_today = sales_result.one()

    # ── 2. Активные заявки (Заказы + Возвраты) ────────────────────────────────
    active_statuses = [
        OrderStatus.PENDING,
        OrderStatus.RETURN_PENDING,
        OrderStatus.DISPLAY_RETURN_PENDING,
        OrderStatus.PARTIAL_APPROVAL_PENDING,
    ]
    pending_result = await session.execute(
        select(func.count(Order.id)).where(Order.status.in_(active_statuses))
    )
    pending_orders = pending_result.scalar() or 0

    # ── 3. Текущий суммарный долг всех магазинов ──────────────────────────────
    debt_result = await session.execute(
        select(func.coalesce(func.sum(Store.current_debt), 0)).where(
            Store.is_active.is_(True)
        )
    )
    total_debt = debt_result.scalar() or Decimal("0")

    # ── 4. Долги по каждому магазину ──────────────────────────────────────────
    stores_result = await session.execute(
        select(Store.id, Store.name, Store.current_debt).where(
            Store.is_active.is_(True)
        )
    )
    store_debts = [
        StoreDebt(store_id=row.id, store_name=row.name, current_debt=row.current_debt)
        for row in stores_result.all()
    ]

    # ── 4B. Долги по оптовикам ────────────────────────────────────────────────
    inv_subq = select(SupplierInvoice.supplier_id, func.sum(SupplierInvoice.total_amount).label('tot')).group_by(SupplierInvoice.supplier_id).subquery()
    pay_subq = select(SupplierPayment.supplier_id, func.sum(SupplierPayment.amount).label('tot')).group_by(SupplierPayment.supplier_id).subquery()
    ret_subq = select(SupplierReturn.supplier_id, func.sum(SupplierReturn.total_amount).label('tot')).group_by(SupplierReturn.supplier_id).subquery()
    
    sup_stmt = (
        select(
            Supplier.id, 
            Supplier.name, 
            func.coalesce(inv_subq.c.tot, 0) - func.coalesce(pay_subq.c.tot, 0) - func.coalesce(ret_subq.c.tot, 0)
        )
        .outerjoin(inv_subq, Supplier.id == inv_subq.c.supplier_id)
        .outerjoin(pay_subq, Supplier.id == pay_subq.c.supplier_id)
        .outerjoin(ret_subq, Supplier.id == ret_subq.c.supplier_id)
        .where(Supplier.is_active.is_(True))
    )
    sup_res = await session.execute(sup_stmt)
    
    supplier_debts = []
    total_supplier_debt = Decimal("0")
    for row in sup_res.all():
        debt = Decimal(row[2])
        if debt > 0:
            supplier_debts.append(SupplierDebt(supplier_id=row[0], supplier_name=row[1], current_debt=debt))
            total_supplier_debt += debt

    # ── 5. Выручка по магазинам за период ─────────────────────────────────────
    if end_date:
        period_condition = and_(Sale.created_at >= start_date, Sale.created_at < end_date)
    else:
        period_condition = Sale.created_at >= start_date

    revenue_stmt = (
        select(
            Store.name,
            func.coalesce(
                func.sum(
                    case(
                        (period_condition, Sale.total_amount),
                        else_=0,
                    )
                ),
                0,
            ),
        )
        .join(Sale, Sale.store_id == Store.id, isouter=True)
        .where(Store.is_active.is_(True))
    )
    revenue_stmt = revenue_stmt.group_by(Store.id, Store.name).order_by(
        func.sum(Sale.total_amount).desc()
    )
    rev_result = await session.execute(revenue_stmt)
    store_revenues = [
        StoreRevenue(store_name=row[0], total_revenue=row[1] or Decimal("0"))
        for row in rev_result.all()
    ]

    # ── 6. Заказы по статусам ─────────────────────────────────────────────────
    status_stmt = select(Order.status, func.count(Order.id)).group_by(Order.status)
    status_result = await session.execute(status_stmt)
    orders_by_status = [
        OrderStatusCount(status=str(row[0].value), count=row[1])
        for row in status_result.all()
    ]

    return DashboardResponse(
        total_orders_today=orders_count,
        total_revenue_today=revenue_today,
        total_debt=total_debt,
        total_supplier_debt=total_supplier_debt,
        pending_orders=pending_orders,
        store_debts=store_debts,
        supplier_debts=supplier_debts,
        store_revenues=store_revenues,
        orders_by_status=orders_by_status,
    )
