from datetime import date, datetime, time
from typing import Any
from aiogram import F, Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FinancialTransactionType
from app.models.financial_transaction import FinancialTransaction
from app.models.user import User

router = Router(name="seller.report")


@router.message(F.text.in_({"📊 Отчет", "📊 Ҳисобот"}))
async def daily_report(
    message: Message, user: User, session: AsyncSession, state: FSMContext, _: Any
) -> None:
    await state.clear()
    today_start = datetime.combine(date.today(), time.min)

    # Sales today
    stmt = (
        select(
            func.count(FinancialTransaction.id),
            func.coalesce(func.sum(FinancialTransaction.amount), 0),
        )
        .where(
            FinancialTransaction.store_id == user.store_id,
            FinancialTransaction.type == FinancialTransactionType.PAYMENT,
            FinancialTransaction.created_at >= today_start,
        )
    )
    result = await session.execute(stmt)
    count, total = result.one()

    store = user.store
    await message.answer(
        _("report_daily_title") + 
        _("report_sales_count", count=count) +
        _("report_sales_amount", total=total) +
        _("report_current_debt", debt=store.current_debt),
        parse_mode="HTML",
    )
