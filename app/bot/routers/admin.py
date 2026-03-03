from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import RoleFilter
from app.bot.keyboards.inline import collection_amount_kb, stores_debt_kb
from app.bot.states.states import CashCollectionFlow
from app.models.enums import UserRole
from app.models.user import User
from app.services import transaction_service

router = Router(name="admin")
router.message.filter(RoleFilter(UserRole.ADMIN))
router.callback_query.filter(RoleFilter(UserRole.ADMIN))




@router.message(F.text == "💸 Начать сбор кассы")
async def start_collection(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    stores = await transaction_service.get_stores_with_debt(session)
    if not stores:
        await message.answer("Нет магазинов с задолженностью. 🎉")
        return
    await message.answer(
        "Выберите магазин для инкассации:",
        reply_markup=stores_debt_kb(stores),
    )
    await state.set_state(CashCollectionFlow.select_store)


@router.callback_query(
    CashCollectionFlow.select_store, F.data.startswith("collect:store:")
)
async def select_store(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    store_id = int(callback.data.split(":")[-1])
    from app.models.store import Store

    store = await session.get(Store, store_id)
    await state.update_data(store_id=store_id, debt=float(store.current_debt))
    await callback.message.edit_text(
        f"🏪 <b>{store.name}</b>\nДолг: {store.current_debt} сом",
        parse_mode="HTML",
        reply_markup=collection_amount_kb(store_id, float(store.current_debt)),
    )
    await callback.answer()




@router.callback_query(F.data.startswith("collect:full:"))
async def collect_full(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    store_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    amount = Decimal(str(data["debt"]))

    async with session.begin():
        txn = await transaction_service.record_cash_collection(
            session, store_id, user.id, amount
        )

    await callback.message.edit_text(
        f"✅ Инкассация завершена!\nСобрано: {txn.amount} сом"
    )
    await state.clear()
    await callback.answer()




@router.callback_query(F.data.startswith("collect:partial:"))
async def collect_partial_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    store_id = int(callback.data.split(":")[-1])
    await state.update_data(store_id=store_id)
    await callback.message.edit_text("Введите сумму, которую забрали (сом):")
    await state.set_state(CashCollectionFlow.enter_amount)
    await callback.answer()


@router.message(CashCollectionFlow.enter_amount)
async def collect_partial_amount(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer("Введите корректную положительную сумму.")
        return

    data = await state.get_data()
    store_id = data["store_id"]

    async with session.begin():
        txn = await transaction_service.record_cash_collection(
            session, store_id, user.id, amount
        )

    from app.models.store import Store
    store = await session.get(Store, store_id)

    await message.answer(
        f"✅ Инкассация: {txn.amount} сом\n"
        f"Остаток долга: {store.current_debt} сом"
    )
    await state.clear()




@router.callback_query(F.data.startswith("collect:skip:"))
async def collect_skip(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await callback.message.edit_text("⏭ Пропущено.")
    await state.clear()
    await callback.answer()




@router.message(F.text == "📝 Список должников")
async def debtors_list(
    message: Message, session: AsyncSession
) -> None:
    stores = await transaction_service.get_stores_with_debt(session)
    if not stores:
        await message.answer("Все магазины чисты! 🎉")
        return

    lines = ["📝 <b>Список должников:</b>\n"]
    total = Decimal("0")
    for s in stores:
        lines.append(f"• 🏪 {s.name}: <b>{s.current_debt}</b> сом")
        total += s.current_debt
    lines.append(f"\n💰 Итого: <b>{total}</b> сом")
    await message.answer("\n".join(lines), parse_mode="HTML")




@router.message(F.text == "📊 Итог сбора")
async def collection_summary(
    message: Message, user: User, session: AsyncSession
) -> None:
    from datetime import date, datetime, time

    from sqlalchemy import func, select

    from app.models.enums import TransactionType
    from app.models.transaction import Transaction

    today_start = datetime.combine(date.today(), time.min)

    stmt = (
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.type == TransactionType.CASH_COLLECTION,
            Transaction.created_at >= today_start,
        )
    )
    result = await session.execute(stmt)
    count, total = result.one()

    await message.answer(
        f"📊 <b>Итог сбора за сегодня</b>\n\n"
        f"Инкассаций: {count}\n"
        f"Собрано: {total} сом",
        parse_mode="HTML",
    )
