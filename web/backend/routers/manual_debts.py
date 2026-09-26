from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import joinedload

from app.models.enums import ManualDebtTransactionType, StoreType
from app.models.manual_debt_transaction import ManualDebtTransaction
from app.models.store import Store
from web.backend.dependencies import AdminUser, SessionDep
from web.backend.schemas.manual_debts import (
    ManualDebtCreate,
    ManualDebtOverview,
    ManualDebtStoreDetail,
    ManualDebtStoreSummary,
    ManualDebtTransactionOut,
    ManualDebtUpdate,
)

router = APIRouter(prefix="/manual-debts", tags=["Manual debts"])
ZERO = Decimal("0.00")


def _signed_amount():
    return case(
        (
            ManualDebtTransaction.type == ManualDebtTransactionType.CHARGE,
            ManualDebtTransaction.amount,
        ),
        else_=-ManualDebtTransaction.amount,
    )


async def _balance(session: SessionDep, store_id: int, exclude_id: int | None = None) -> Decimal:
    stmt = select(func.coalesce(func.sum(_signed_amount()), 0)).where(
        ManualDebtTransaction.store_id == store_id
    )
    if exclude_id is not None:
        stmt = stmt.where(ManualDebtTransaction.id != exclude_id)
    result = await session.execute(stmt)
    return Decimal(result.scalar_one()).quantize(Decimal("0.01"))


async def _get_store_for_update(session: SessionDep, store_id: int) -> Store:
    result = await session.execute(
        select(Store)
        .where(
            Store.id == store_id,
            Store.store_type == StoreType.STORE,
            Store.is_active.is_(True),
        )
        .with_for_update()
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Активный магазин не найден",
        )
    return store


def _transaction_out(transaction: ManualDebtTransaction) -> ManualDebtTransactionOut:
    return ManualDebtTransactionOut(
        id=transaction.id,
        store_id=transaction.store_id,
        store_name=transaction.store.name,
        user_id=transaction.user_id,
        user_name=transaction.user.name,
        type=transaction.type,
        amount=transaction.amount,
        operation_date=transaction.operation_date,
        comment=transaction.comment,
        created_at=transaction.created_at,
    )


def _clean_comment(comment: str | None) -> str | None:
    if comment is None:
        return None
    cleaned = comment.strip()
    return cleaned or None


@router.get("", response_model=ManualDebtOverview)
async def get_manual_debts(
    session: SessionDep,
    current_user: AdminUser,
) -> ManualDebtOverview:
    stores_result = await session.execute(
        select(Store)
        .where(Store.store_type == StoreType.STORE, Store.is_active.is_(True))
        .order_by(Store.name)
    )
    stores = stores_result.scalars().all()

    transactions_result = await session.execute(
        select(ManualDebtTransaction)
        .options(
            joinedload(ManualDebtTransaction.store),
            joinedload(ManualDebtTransaction.user),
        )
        .join(Store, Store.id == ManualDebtTransaction.store_id)
        .where(Store.store_type == StoreType.STORE, Store.is_active.is_(True))
        .order_by(
            ManualDebtTransaction.operation_date.desc(),
            ManualDebtTransaction.id.desc(),
        )
    )
    transactions = transactions_result.scalars().all()

    balances: dict[int, Decimal] = {store.id: ZERO for store in stores}
    latest: dict[int, ManualDebtTransaction] = {}
    month_start = date.today().replace(day=1)
    charged_this_month = ZERO
    for transaction in transactions:
        change = transaction.amount
        if transaction.type == ManualDebtTransactionType.PAYMENT:
            change = -change
        balances[transaction.store_id] += change
        latest.setdefault(transaction.store_id, transaction)
        if (
            transaction.type == ManualDebtTransactionType.CHARGE
            and transaction.operation_date >= month_start
        ):
            charged_this_month += transaction.amount

    items = [
        ManualDebtStoreSummary(
            store_id=store.id,
            store_name=store.name,
            balance=balances[store.id],
            last_transaction=(
                _transaction_out(latest[store.id]) if store.id in latest else None
            ),
        )
        for store in stores
    ]
    items.sort(key=lambda item: (-item.balance, item.store_name.casefold()))

    return ManualDebtOverview(
        stores=items,
        stores_with_debt=sum(item.balance > ZERO for item in items),
        total_debt=sum((item.balance for item in items), ZERO),
        charged_this_month=charged_this_month,
    )


@router.get("/stores/{store_id}", response_model=ManualDebtStoreDetail)
async def get_manual_debt_store(
    store_id: int,
    session: SessionDep,
    current_user: AdminUser,
) -> ManualDebtStoreDetail:
    store_result = await session.execute(
        select(Store).where(
            Store.id == store_id,
            Store.store_type == StoreType.STORE,
            Store.is_active.is_(True),
        )
    )
    store = store_result.scalar_one_or_none()
    if store is None:
        raise HTTPException(status_code=404, detail="Активный магазин не найден")

    result = await session.execute(
        select(ManualDebtTransaction)
        .options(
            joinedload(ManualDebtTransaction.store),
            joinedload(ManualDebtTransaction.user),
        )
        .where(ManualDebtTransaction.store_id == store_id)
        .order_by(
            ManualDebtTransaction.operation_date.desc(),
            ManualDebtTransaction.id.desc(),
        )
    )
    transactions = result.scalars().all()
    return ManualDebtStoreDetail(
        store_id=store.id,
        store_name=store.name,
        balance=await _balance(session, store.id),
        transactions=[_transaction_out(item) for item in transactions],
    )


async def _create_transaction(
    payload: ManualDebtCreate,
    transaction_type: ManualDebtTransactionType,
    session: SessionDep,
    current_user: AdminUser,
) -> ManualDebtTransactionOut:
    await _get_store_for_update(session, payload.store_id)
    if transaction_type == ManualDebtTransactionType.PAYMENT:
        balance = await _balance(session, payload.store_id)
        if payload.amount > balance:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Оплата не может превышать ручной долг магазина",
            )

    transaction = ManualDebtTransaction(
        store_id=payload.store_id,
        user_id=current_user.id,
        type=transaction_type,
        amount=payload.amount,
        operation_date=payload.operation_date,
        comment=_clean_comment(payload.comment),
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction, ["store", "user"])
    return _transaction_out(transaction)


@router.post("/charges", response_model=ManualDebtTransactionOut, status_code=201)
async def create_charge(
    payload: ManualDebtCreate,
    session: SessionDep,
    current_user: AdminUser,
) -> ManualDebtTransactionOut:
    return await _create_transaction(
        payload, ManualDebtTransactionType.CHARGE, session, current_user
    )


@router.post("/payments", response_model=ManualDebtTransactionOut, status_code=201)
async def create_payment(
    payload: ManualDebtCreate,
    session: SessionDep,
    current_user: AdminUser,
) -> ManualDebtTransactionOut:
    return await _create_transaction(
        payload, ManualDebtTransactionType.PAYMENT, session, current_user
    )


@router.patch("/transactions/{transaction_id}", response_model=ManualDebtTransactionOut)
async def update_transaction(
    transaction_id: int,
    payload: ManualDebtUpdate,
    session: SessionDep,
    current_user: AdminUser,
) -> ManualDebtTransactionOut:
    result = await session.execute(
        select(ManualDebtTransaction)
        .options(
            joinedload(ManualDebtTransaction.store),
            joinedload(ManualDebtTransaction.user),
        )
        .where(ManualDebtTransaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Операция не найдена")

    await _get_store_for_update(session, transaction.store_id)
    amount = payload.amount if payload.amount is not None else transaction.amount
    balance_without = await _balance(session, transaction.store_id, transaction.id)
    resulting_balance = balance_without + (
        amount
        if transaction.type == ManualDebtTransactionType.CHARGE
        else -amount
    )
    if resulting_balance < ZERO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Изменение приведёт к переплате по ручному долгу",
        )

    transaction.amount = amount
    if payload.operation_date is not None:
        transaction.operation_date = payload.operation_date
    if "comment" in payload.model_fields_set:
        transaction.comment = _clean_comment(payload.comment)
    await session.commit()
    await session.refresh(transaction, ["store", "user"])
    return _transaction_out(transaction)


@router.delete("/transactions/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int,
    session: SessionDep,
    current_user: AdminUser,
) -> Response:
    result = await session.execute(
        select(ManualDebtTransaction).where(
            ManualDebtTransaction.id == transaction_id
        )
    )
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Операция не найдена")

    await _get_store_for_update(session, transaction.store_id)
    balance_without = await _balance(session, transaction.store_id, transaction.id)
    if balance_without < ZERO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала удалите или измените оплаты, связанные с этим долгом",
        )

    await session.delete(transaction)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
