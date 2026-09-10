import math

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.models.enums import FinancialTransactionType
from app.models.financial_transaction import FinancialTransaction
from app.models.store import Store
from app.services.transaction_service import TransactionService
from web.backend.dependencies import AdminUser, SessionDep
from web.backend.schemas.finance import (
    CashCollectionHistoryItem,
    CashCollectionRequest,
    CashCollectionSummary,
    PaginatedCashCollectionHistory,
)

router = APIRouter(prefix="/finance", tags=["Finance"])


@router.get(
    "/debtors",
    response_model=list[CashCollectionSummary],
    summary="Списки магазинов с долгами",
    description="Возвращает список магазинов, у которых есть текущий долг больше 0.",
)
async def get_debtors(
    session: SessionDep,
    current_user: AdminUser,
) -> list[CashCollectionSummary]:
    stmt = (
        select(Store)
        .where(Store.is_active.is_(True), Store.current_debt > 0)
        .order_by(Store.current_debt.desc())
    )
    result = await session.execute(stmt)
    stores = result.scalars().all()

    return [
        {
            "store_id": st.id,
            "store_name": st.name,
            "current_debt": st.current_debt,
        }
        for st in stores
    ]


@router.get(
    "/history",
    response_model=PaginatedCashCollectionHistory,
    summary="История инкассаций",
    description="Возвращает операции по сбору наличных (CASH_COLLECTION) с пагинацией.",
)
async def get_collection_history(
    session: SessionDep,
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
) -> PaginatedCashCollectionHistory:
    base_filter = FinancialTransaction.type == FinancialTransactionType.COLLECTION

    total_res = await session.execute(
        select(func.count(FinancialTransaction.id)).where(base_filter)
    )
    total = int(total_res.scalar() or 0)
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    stmt = (
        select(FinancialTransaction)
        .options(joinedload(FinancialTransaction.store), joinedload(FinancialTransaction.user))
        .where(base_filter)
        .order_by(FinancialTransaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    txns = result.scalars().all()

    items = [
        CashCollectionHistoryItem(
            id=txn.id,
            store_id=txn.store_id,
            store_name=txn.store.name if txn.store else "—",
            user_id=txn.user_id,
            user_name=txn.user.name if txn.user else "—",
            amount=txn.amount,
            created_at=txn.created_at,
        )
        for txn in txns
    ]

    return PaginatedCashCollectionHistory(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/collect",
    response_model=CashCollectionHistoryItem,
    summary="Оформить сбор денег",
    description="Списывает указанную сумму из долга магазина и записывает операцию в историю.",
)
async def collect_cash(
    request: CashCollectionRequest,
    session: SessionDep,
    current_user: AdminUser,
) -> CashCollectionHistoryItem:
    txn_service = TransactionService(session)

    try:
        # TransactionService.record_cash_collection internally deducts the store's current_debt
        # via record_debt_ledger with a negative amount change.
        txn = await txn_service.record_cash_collection(
            store_id=request.store_id,
            admin_user_id=current_user.id,
            amount=request.amount,
        )
        await session.commit()
        await session.refresh(txn, ["store", "user"])

        return {
            "id": txn.id,
            "store_id": txn.store_id,
            "store_name": txn.store.name if txn.store else "—",
            "user_id": txn.user_id,
            "user_name": txn.user.name if txn.user else "—",
            "amount": txn.amount,
            "created_at": txn.created_at,
        }
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
