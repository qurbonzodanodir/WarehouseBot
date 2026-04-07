from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.enums import FinancialTransactionType
from app.models.financial_transaction import FinancialTransaction
from app.models.store import Store
from app.services.transaction_service import TransactionService
from web.backend.dependencies import AdminUser, CurrentUser, SessionDep
from web.backend.schemas.finance import (
    CashCollectionHistoryItem,
    CashCollectionRequest,
    CashCollectionSummary,
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
    response_model=list[CashCollectionHistoryItem],
    summary="История инкассаций",
    description="Возвращает последние операции по сбору наличных (CASH_COLLECTION).",
)
async def get_collection_history(
    session: SessionDep,
    current_user: AdminUser,
    limit: int = 50,
) -> list[CashCollectionHistoryItem]:
    stmt = (
        select(FinancialTransaction)
        .options(joinedload(FinancialTransaction.store), joinedload(FinancialTransaction.user))
        .where(FinancialTransaction.type == FinancialTransactionType.COLLECTION)
        .order_by(FinancialTransaction.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    txns = result.scalars().all()

    return [
        {
            "id": txn.id,
            "store_id": txn.store_id,
            "store_name": txn.store.name if txn.store else "—",
            "user_id": txn.user_id,
            "user_name": txn.user.name if txn.user else "—",
            "amount": txn.amount,
            "created_at": txn.created_at,
        }
        for txn in txns
    ]


@router.post(
    "/collect",
    response_model=CashCollectionHistoryItem,
    summary="Оформить сбор денег",
    description="Списывает указанную сумму из долга магазина и записывает операцию в историю.",
)
async def collect_cash(
    request: CashCollectionRequest,
    session: SessionDep,
    current_user: CurrentUser,
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
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
