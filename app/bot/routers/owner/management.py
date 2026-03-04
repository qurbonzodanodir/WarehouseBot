from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.bot.keyboards.inline import (
    employees_list_kb,
    invite_role_kb,
    invite_stores_kb,
    management_menu_kb,
    stores_list_kb,
)
from app.bot.states.states import AddStoreFlow, InviteFlow
from app.models.enums import TransactionType, UserRole
from app.models.store import Store
from app.models.transaction import Transaction
from app.models.user import User
from app.services import invite_service, store_service, transaction_service

router = Router(name="owner.management")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ Управление (Main menu)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text == "⚙️ Управление")
async def management_panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "⚙️ <b>Управление системой</b>",
        parse_mode="HTML",
        reply_markup=management_menu_kb(),
    )


@router.callback_query(F.data == "mgmt:back")
async def mgmt_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>Управление системой</b>",
        parse_mode="HTML",
        reply_markup=management_menu_kb(),
    )
    await callback.answer()


# ─── 🏢 Магазины ─────────────────────────────────────────────────────


@router.callback_query(F.data == "mgmt:stores")
async def mgmt_stores(callback: CallbackQuery, session: AsyncSession) -> None:
    stores = await store_service.list_active_stores(session)
    await callback.message.edit_text(
        "🏢 <b>Магазины</b>",
        parse_mode="HTML",
        reply_markup=stores_list_kb(stores),
    )
    await callback.answer()


@router.callback_query(F.data == "mgmt:add_store")
async def mgmt_add_store(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "Введите <b>название</b> нового магазина:", parse_mode="HTML"
    )
    await state.set_state(AddStoreFlow.enter_name)
    await callback.answer()


@router.message(AddStoreFlow.enter_name)
async def store_enter_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    await state.update_data(store_name=name)
    await message.answer(
        f"Название: <b>{name}</b>\n\nТеперь введите <b>адрес</b> магазина:",
        parse_mode="HTML",
    )
    await state.set_state(AddStoreFlow.enter_address)


@router.message(AddStoreFlow.enter_address)
async def store_enter_address(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    address = message.text.strip()
    data = await state.get_data()
    name = data["store_name"]

    new_store = await store_service.create_store(session, name, address)
    await session.commit()

    await message.answer(
        f"✅ Магазин добавлен!\n\n"
        f"🏢 {name}\n"
        f"📍 {address}\n"
        f"ID: {new_store.id}",
    )
    await state.clear()


# ─── 👥 Сотрудники ──────────────────────────────────────────────────


@router.callback_query(F.data == "mgmt:employees")
async def mgmt_employees(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await session.execute(
        select(User)
        .options(joinedload(User.store))
        .where(User.is_active.is_(True))
        .order_by(User.role, User.name)
    )
    users = result.scalars().all()
    await callback.message.edit_text(
        "👥 <b>Сотрудники</b>",
        parse_mode="HTML",
        reply_markup=employees_list_kb(users),
    )
    await callback.answer()


# ─── ➕ Пригласить сотрудника (Invite Flow) ──────────────────────────


@router.callback_query(F.data == "mgmt:invite")
async def invite_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    stores = await store_service.list_active_stores(session)
    if not stores:
        await callback.message.edit_text("Сначала добавьте магазин!")
        await callback.answer()
        return
    await callback.message.edit_text(
        "Выберите <b>магазин</b> для нового сотрудника:",
        parse_mode="HTML",
        reply_markup=invite_stores_kb(stores),
    )
    await state.set_state(InviteFlow.select_store)
    await callback.answer()


@router.callback_query(InviteFlow.select_store, F.data.startswith("invite:store:"))
async def invite_select_store(callback: CallbackQuery, state: FSMContext) -> None:
    store_id = int(callback.data.split(":")[-1])
    await state.update_data(store_id=store_id)
    await callback.message.edit_text(
        "Выберите <b>роль</b> для нового сотрудника:",
        parse_mode="HTML",
        reply_markup=invite_role_kb(),
    )
    await state.set_state(InviteFlow.select_role)
    await callback.answer()


@router.callback_query(InviteFlow.select_role, F.data.startswith("invite:role:"))
async def invite_select_role(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    role_str = callback.data.split(":")[-1]
    role = UserRole(role_str)
    data = await state.get_data()
    store_id = data["store_id"]

    invite = await invite_service.create_invite(session, role, store_id)
    await session.commit()

    store = await session.get(Store, store_id)
    role_name = {"seller": "🛒 Продавец", "warehouse": "🏭 Складщик"}.get(
        role_str, role_str
    )

    await callback.message.edit_text(
        f"✅ <b>Код приглашения создан!</b>\n\n"
        f"📋 Код: <code>{invite.code}</code>\n"
        f"🏢 Магазин: {store.name}\n"
        f"👤 Роль: {role_name}\n"
        f"⏰ Действует 24 часа\n\n"
        f"Отправьте этот код сотруднику.\n"
        f"Он введёт его при первом /start в боте.",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


# ─── 📋 Должники ────────────────────────────────────────────────────


@router.callback_query(F.data == "mgmt:debtors")
async def mgmt_debtors(callback: CallbackQuery, session: AsyncSession) -> None:
    stores = await transaction_service.get_stores_with_debt(session)
    if not stores:
        await callback.message.edit_text(
            "Все магазины чисты! 🎉",
            reply_markup=management_menu_kb(),
        )
        await callback.answer()
        return

    lines = ["📋 <b>Должники:</b>\n"]
    total = Decimal("0")
    for s in stores:
        lines.append(f"• 🏪 {s.name}: <b>{s.current_debt}</b> сом")
        total += s.current_debt
    lines.append(f"\n💰 Итого: <b>{total}</b> сом")

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="mgmt:back"))

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


# ─── 🏆 Рейтинг ─────────────────────────────────────────────────────


@router.callback_query(F.data == "mgmt:rating")
async def mgmt_rating(callback: CallbackQuery, session: AsyncSession) -> None:
    from datetime import date, datetime, time

    today_start = datetime.combine(date.today(), time.min)

    stmt = (
        select(
            Store.name,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .join(Transaction, Transaction.store_id == Store.id, isouter=True)
        .where(
            Store.is_active.is_(True),
            Transaction.type == TransactionType.SALE,
            Transaction.created_at >= today_start,
        )
        .group_by(Store.id, Store.name)
        .order_by(func.sum(Transaction.amount).desc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="mgmt:back"))

    if not rows:
        await callback.message.edit_text(
            "Нет данных за сегодня.",
            reply_markup=builder.as_markup(),
        )
        await callback.answer()
        return

    lines = ["🏆 <b>Рейтинг магазинов (сегодня):</b>\n"]
    for i, (name, total) in enumerate(rows, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        lines.append(f"{medal} {name} — {total} сом")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()
