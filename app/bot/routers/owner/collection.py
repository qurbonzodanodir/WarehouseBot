from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import collection_amount_kb, stores_debt_kb
from app.bot.states.states import CashCollectionFlow
from app.models.store import Store
from app.models.user import User
from app.services import transaction_service

router = Router(name="owner.collection")


@router.message(F.text == "💰 Инкассация")
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
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession,
) -> None:
    store_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    amount = Decimal(str(data["debt"]))

    txn = await transaction_service.record_cash_collection(
        session, store_id, user.id, amount
    )
    await session.commit()

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
    message: Message, state: FSMContext, user: User, session: AsyncSession,
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

    txn = await transaction_service.record_cash_collection(
        session, store_id, user.id, amount
    )
    await session.commit()

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
