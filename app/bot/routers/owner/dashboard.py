from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, time, timedelta, timezone

from app.models.enums import FinancialTransactionType
from app.models.store import Store
from app.models.financial_transaction import FinancialTransaction
from app.models.order import Order
from app.models.enums import OrderStatus

from app.bot.keyboards import reply
from app.core.i18n import Translator

router = Router(name="owner.dashboard")


def _get_dashboard_kb(_) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_("period_today"), callback_data="dash:today"),
        InlineKeyboardButton(text=_("period_yesterday"), callback_data="dash:yesterday"),
    )
    builder.row(
        InlineKeyboardButton(text=_("period_week"), callback_data="dash:week"),
        InlineKeyboardButton(text=_("period_month"), callback_data="dash:month"),
    )
    return builder


async def _get_dashboard_text(session: AsyncSession, period: str, _: Any) -> str:
    now_utc = datetime.now(timezone.utc)
    today_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    
    start_date = today_start
    end_date = None
    period_name_key = "period_today"

    if period == "yesterday":
        start_date = today_start - timedelta(days=1)
        end_date = today_start
        period_name_key = "period_yesterday"
    elif period == "week":
        start_date = today_start - timedelta(days=7)
        period_name_key = "period_week"
    elif period == "month":
        start_date = today_start - timedelta(days=30)
        period_name_key = "period_month"

    period_name = _(period_name_key)

    # 1. Sales
    sales_stmt = select(
        func.count(FinancialTransaction.id),
        func.coalesce(func.sum(FinancialTransaction.amount), 0),
    ).where(
        FinancialTransaction.type == FinancialTransactionType.PAYMENT,
        FinancialTransaction.created_at >= start_date,
    )
    if end_date:
        sales_stmt = sales_stmt.where(FinancialTransaction.created_at < end_date)
    
    sales_result = await session.execute(sales_stmt)
    sales_count, sales_total = sales_result.one()

    # 2. Returns
    from app.models.stock_movement import StockMovement
    from app.models.product import Product
    from app.models.enums import StockMovementType

    returns_stmt = (
        select(
            func.count(StockMovement.id),
            func.coalesce(func.sum(StockMovement.quantity * Product.price), 0),
        )
        .join(Product, StockMovement.product_id == Product.id)
        .where(
            StockMovement.movement_type.in_([
                StockMovementType.RETURN_TO_WAREHOUSE,
                StockMovementType.DISPLAY_RETURN
            ]),
            StockMovement.created_at >= start_date,
        )
    )
    if end_date:
        returns_stmt = returns_stmt.where(StockMovement.created_at < end_date)
        
    returns_result = await session.execute(returns_stmt)
    returns_count, returns_total = returns_result.one()

    # 3. Cash Collections
    coll_stmt = select(
        func.count(FinancialTransaction.id),
        func.coalesce(func.sum(FinancialTransaction.amount), 0),
    ).where(
        FinancialTransaction.type == FinancialTransactionType.COLLECTION,
        FinancialTransaction.created_at >= start_date,
    )
    if end_date:
        coll_stmt = coll_stmt.where(FinancialTransaction.created_at < end_date)
        
    coll_result = await session.execute(coll_stmt)
    coll_count, coll_total = coll_result.one()

    # 4. Total Network Debt (Always current)
    debt_stmt = select(
        func.coalesce(func.sum(Store.current_debt), 0)
    ).where(Store.is_active.is_(True))
    debt_result = await session.execute(debt_stmt)
    total_debt = debt_result.scalar()

    return (
        _("dash_report", period=period_name) + "\n\n" +
        _("dash_sales", total=f"{sales_total:,.0f}", count=sales_count) + "\n" +
        _("dash_collections", total=f"{coll_total:,.0f}", count=coll_count) + "\n" +
        _("dash_returns", total=f"{returns_total:,.0f}", count=returns_count) + "\n\n" +
        _("dash_total_debt", total=f"{total_debt:,.2f}") + "\n" +
        "────────────────────\n" +
        _("dash_select_period")
    )


@router.message(F.text.in_({"📊 Дашборд", "📊 Дашборд"})) # Tajik button is same emoji but might change
async def dashboard_command(message: Message, session: AsyncSession, _: Any) -> None:
    # If TG button is different, we'll need to update F.text filter. 
    # For now, btn_dashboard is "📊 Дашборд" in both.
    text = await _get_dashboard_text(session, "today", _)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_get_dashboard_kb(_).as_markup(),
    )


@router.callback_query(F.data.startswith("dash:"))
async def dashboard_callback(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    period = callback.data.split(":")[1]
    text = await _get_dashboard_text(session, period, _)
    
    # Only edit if text is different to avoid errors
    if callback.message.text != text:
        try:
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=_get_dashboard_kb(_).as_markup(),
            )
        except Exception:
            pass
    await callback.answer()
