from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionType
from app.models.store import Store
from app.models.transaction import Transaction

router = Router(name="owner.dashboard")


@router.message(F.text == "📊 Дашборд")
async def dashboard(message: Message, session: AsyncSession) -> None:
    from datetime import date, datetime, time

    today_start = datetime.combine(date.today(), time.min)

    sales_stmt = (
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        ).where(
            Transaction.type == TransactionType.SALE,
            Transaction.created_at >= today_start,
        )
    )
    sales_result = await session.execute(sales_stmt)
    sales_count, sales_total = sales_result.one()

    coll_stmt = (
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        ).where(
            Transaction.type == TransactionType.CASH_COLLECTION,
            Transaction.created_at >= today_start,
        )
    )
    coll_result = await session.execute(coll_stmt)
    coll_count, coll_total = coll_result.one()

    debt_stmt = select(
        func.coalesce(func.sum(Store.current_debt), 0)
    ).where(Store.is_active.is_(True))
    debt_result = await session.execute(debt_stmt)
    total_debt = debt_result.scalar()

    await message.answer(
        f"📊 <b>Дашборд</b>\n\n"
        f"💰 Продажи сегодня: {sales_count} на {sales_total} сом\n"
        f"💸 Инкассация: {coll_count} на {coll_total} сом\n"
        f"📊 Общий долг сети: {total_debt} сом",
        parse_mode="HTML",
    )
