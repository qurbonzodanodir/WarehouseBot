from decimal import Decimal
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.bot.keyboards import reply
from app.bot.keyboards.inline import (
    confirm_delete_store_kb,
    confirm_delete_user_kb,
    employee_mgmt_kb,
    employees_list_kb,
    invite_role_kb,
    invite_stores_kb,
    store_mgmt_kb,
    stores_list_kb,
)
from app.bot.states.states import AddStoreFlow, EditStoreFlow, EditEmployeeFlow, InviteFlow
from app.models.enums import FinancialTransactionType, UserRole
from app.models.store import Store
from app.models.financial_transaction import FinancialTransaction
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services import InviteService, StoreService, TransactionService, UserService

router = Router(name="owner.management")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ Управление (Main menu)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.message(F.text.in_({"⚙️ Управление", "⚙️ Идоракунӣ"}))
async def mgmt_main(message: Message, _: Any) -> None:
    await message.answer(
        _("btn_management"),
        reply_markup=reply.get_owner_mgmt_menu(_),
    )


@router.callback_query(F.data == "mgmt:main")
async def mgmt_main_callback(callback: CallbackQuery, _: Any) -> None:
    await callback.message.edit_text(
        _("btn_management"),
        reply_markup=reply.get_owner_mgmt_menu(_),
    )
    await callback.answer()


@router.callback_query(F.data == "mgmt:back")
async def mgmt_back(callback: CallbackQuery, _: Any) -> None:
    await callback.message.delete()
    await callback.message.answer(
        _("btn_management"),
        reply_markup=reply.get_owner_mgmt_menu(_),
    )
    await callback.answer()


@router.message(F.text.in_({"🔙 Назад", "🔙 Ба қафо"}))
async def mgmt_back_text(message: Message, state: FSMContext, _: Any) -> None:
    await state.clear()
    await message.answer(
        _("welcome", name=message.from_user.full_name, greeting=_("menu_owner")),
        reply_markup=reply.get_owner_menu(_),
    )

# ─── 🏢 Магазины ─────────────────────────────────────────────────────


@router.message(F.text.in_({"🏢 Магазины", "🏢 Мағозаҳо"}))
async def mgmt_stores(message: Message, session: AsyncSession, _: Any) -> None:
    store_svc = StoreService(session)
    stores = await store_svc.list_active_stores()
    await message.answer(
        _("mgmt_stores_title"),
        parse_mode="HTML",
        reply_markup=stores_list_kb(stores, _=_),
    )

@router.callback_query(F.data == "mgmt:stores")
async def mgmt_stores_callback(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    store_svc = StoreService(session)
    stores = await store_svc.list_active_stores()
    await callback.message.edit_text(
        _("mgmt_stores_title"),
        parse_mode="HTML",
        reply_markup=stores_list_kb(stores, _=_),
    )
    await callback.answer()


@router.callback_query(F.data == "mgmt:add_store")
async def mgmt_add_store(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.message.edit_text(
        _("mgmt_store_add_name"), parse_mode="HTML"
    )
    await state.set_state(AddStoreFlow.enter_name)
    await callback.answer()


@router.message(AddStoreFlow.enter_name)
async def store_enter_name(message: Message, state: FSMContext, _: Any) -> None:
    name = message.text.strip()
    if len(name) < 3 or len(name) > 50:
        await message.answer(_("mgmt_store_invalid_name"))
        return
        
    await state.update_data(store_name=name)
    await message.answer(
        _("mgmt_store_add_addr", name=name),
        parse_mode="HTML",
    )
    await state.set_state(AddStoreFlow.enter_address)


@router.message(AddStoreFlow.enter_address)
async def store_enter_address(
    message: Message, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    address = message.text.strip()
    if len(address) > 100:
        await message.answer(_("mgmt_store_invalid_addr"))
        return
        
    data = await state.get_data()
    name = data["store_name"]

    store_svc = StoreService(session)
    new_store = await store_svc.create_store(name, address)
    await session.commit()

    await message.answer(
        _("mgmt_store_add_success", name=name, address=address, id=new_store.id),
    )
    await state.clear()


# ─── 🏢 Управление конкретным магазином ──────────────────────────────


@router.callback_query(F.data.startswith("mgmt:store:"))
async def mgmt_store_detail(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    store_id = int(callback.data.split(":")[-1])
    store = await session.get(Store, store_id)
    if not store:
        await callback.answer(_("mgmt_store_not_found"))
        return

    from app.bot.keyboards.inline import store_mgmt_kb
    await callback.message.edit_text(
        _("mgmt_store_detail", name=store.name, address=store.address, debt=store.current_debt, id=store.id),
        parse_mode="HTML",
        reply_markup=store_mgmt_kb(store.id, _=_),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mgmt:edit_store_name:"))
async def mgmt_edit_store_name(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    store_id = int(callback.data.split(":")[-1])
    await state.update_data(store_id=store_id)
    await callback.message.edit_text(_("mgmt_store_edit_name"), parse_mode="HTML")
    await state.set_state(EditStoreFlow.enter_name)
    await callback.answer()


@router.message(EditStoreFlow.enter_name)
async def store_edit_name_confirm(message: Message, state: FSMContext, session: AsyncSession, _: Any) -> None:
    name = message.text.strip()
    if len(name) < 3 or len(name) > 50:
        await message.answer(_("mgmt_store_invalid_name"))
        return

    data = await state.get_data()
    store_id = data["store_id"]
    
    store_svc = StoreService(session)
    await store_svc.update_store(store_id, name=name)
    await session.commit()
    
    await message.answer(_("mgmt_store_name_changed", name=name), parse_mode="HTML")
    await state.clear()
    # Return to store list
    stores = await store_svc.list_active_stores()
    await message.answer(_("mgmt_stores_title"), parse_mode="HTML", reply_markup=stores_list_kb(stores, _=_))


@router.callback_query(F.data.startswith("mgmt:edit_store_addr:"))
async def mgmt_edit_store_addr(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    store_id = int(callback.data.split(":")[-1])
    await state.update_data(store_id=store_id)
    await callback.message.edit_text(_("mgmt_store_edit_addr"), parse_mode="HTML")
    await state.set_state(EditStoreFlow.enter_address)
    await callback.answer()


@router.message(EditStoreFlow.enter_address)
async def store_edit_addr_confirm(message: Message, state: FSMContext, session: AsyncSession, _: Any) -> None:
    address = message.text.strip()
    if len(address) > 100:
        await message.answer(_("mgmt_store_invalid_addr"))
        return

    data = await state.get_data()
    store_id = data["store_id"]
    
    store_svc = StoreService(session)
    await store_svc.update_store(store_id, address=address)
    await session.commit()
    
    await message.answer(_("mgmt_store_addr_changed", address=address), parse_mode="HTML")
    await state.clear()
    # Return to store list
    stores = await store_svc.list_active_stores()
    await message.answer(_("mgmt_stores_title"), parse_mode="HTML", reply_markup=stores_list_kb(stores, _=_))


@router.callback_query(F.data.startswith("mgmt:delete_store_ask:"))
async def mgmt_delete_store_ask(callback: CallbackQuery, _: Any) -> None:
    store_id = int(callback.data.split(":")[-1])
    from app.bot.keyboards.inline import confirm_delete_store_kb
    await callback.message.edit_text(
        _("mgmt_store_delete_ask"),
        parse_mode="HTML",
        reply_markup=confirm_delete_store_kb(store_id, _=_),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mgmt:delete_store_conf:"))
async def mgmt_delete_store_conf(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    store_id = int(callback.data.split(":")[-1])
    store_svc = StoreService(session)
    await store_svc.delete_store(store_id)
    await session.commit()
    
    await callback.message.edit_text(_("mgmt_store_delete_success"))
    # Return to store list
    stores = await store_svc.list_active_stores()
    await callback.message.answer(_("mgmt_stores_title"), parse_mode="HTML", reply_markup=stores_list_kb(stores, _=_))
    await callback.answer()


# ─── 👤 Управление конкретным сотрудником ───────────────────────────


@router.callback_query(F.data.startswith("mgmt:employee:"))
async def mgmt_employee_detail(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    user_id = int(callback.data.split(":")[-1])
    user = await session.execute(
        select(User).options(joinedload(User.store)).where(User.id == user_id)
    )
    user = user.scalar_one_or_none()
    
    if not user:
        await callback.answer(_("empl_not_found"))
        return

    role_name = {
        "seller": _("role_seller"), 
        "warehouse": _("role_warehouse"), 
        "owner": _("role_owner")
    }.get(user.role.value, user.role.value)

    if user.role == UserRole.OWNER:
        store_name = _("all_stores")
    else:
        store_name = user.store.name if user.store else "—"

    from app.bot.keyboards.inline import employee_mgmt_kb
    await callback.message.edit_text(
        _("mgmt_empl_detail", name=user.name, role=role_name, store=store_name, id=user.id),
        parse_mode="HTML",
        reply_markup=employee_mgmt_kb(user.id, user.role, _=_),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mgmt:edit_user_store:"))
async def mgmt_edit_user_store(callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any) -> None:
    user_id = int(callback.data.split(":")[-1])
    await state.update_data(edit_user_id=user_id)
    
    store_svc = StoreService(session)
    stores = await store_svc.list_active_stores()
    
    from app.bot.keyboards.inline import invite_stores_kb
    await callback.message.edit_text(
        _("mgmt_empl_edit_store"),
        parse_mode="HTML",
        reply_markup=invite_stores_kb(stores, back_data=f"mgmt:employee:{user_id}", _=_),
    )
    await state.set_state(EditEmployeeFlow.select_store)
    await callback.answer()


@router.callback_query(EditEmployeeFlow.select_store, F.data.startswith("invite:store:"))
async def mgmt_edit_user_store_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any) -> None:
    store_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    user_id = data["edit_user_id"]
    
    user_svc = UserService(session)
    await user_svc.update_user(user_id, store_id=store_id)
    await session.commit()
    
    store = await session.get(Store, store_id)
    await callback.message.edit_text(_("mgmt_empl_store_changed", name=store.name), parse_mode="HTML")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("mgmt:edit_user_role:"))
async def mgmt_edit_user_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any) -> None:
    user_id = int(callback.data.split(":")[-1])
    await state.update_data(edit_user_id=user_id)
    
    user = await session.get(User, user_id)
    if not user:
        await callback.answer(_("empl_not_found"))
        return

    # Check if user's store is the warehouse
    store_svc = StoreService(session)
    main_wh_id = await store_svc.get_main_warehouse_id()
    is_warehouse = (user.store_id == main_wh_id)
    
    from app.bot.keyboards.inline import invite_role_kb
    await callback.message.edit_text(
        _("mgmt_empl_edit_role"),
        parse_mode="HTML",
        reply_markup=invite_role_kb(is_warehouse=is_warehouse, _=_),
    )
    await state.set_state(EditEmployeeFlow.select_role)
    await callback.answer()


@router.callback_query(EditEmployeeFlow.select_role, F.data.startswith("invite:role:"))
async def mgmt_edit_user_role_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any) -> None:
    role_str = callback.data.split(":")[-1]
    role = UserRole(role_str)
    data = await state.get_data()
    user_id = data["edit_user_id"]
    
    user_svc = UserService(session)
    await user_svc.update_user(user_id, role=role)
    await session.commit()
    
    role_name = {"seller": _("role_seller"), "warehouse": _("role_warehouse")}.get(role_str, role_str)
    await callback.message.edit_text(_("mgmt_empl_role_changed", name=role_name), parse_mode="HTML")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("mgmt:delete_user_ask:"))
async def mgmt_delete_user_ask(callback: CallbackQuery, _: Any) -> None:
    user_id = int(callback.data.split(":")[-1])
    from app.bot.keyboards.inline import confirm_delete_user_kb
    await callback.message.edit_text(
        _("mgmt_empl_delete_ask"),
        parse_mode="HTML",
        reply_markup=confirm_delete_user_kb(user_id, _=_),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mgmt:delete_user_conf:"))
async def mgmt_delete_user_conf(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    user_id = int(callback.data.split(":")[-1])
    user_svc = UserService(session)
    await user_svc.delete_user(user_id)
    await session.commit()
    
    await callback.message.edit_text(_("mgmt_empl_delete_success"))
    await callback.answer()


# ─── 📋 Должники ────────────────────────────────────────────────────


@router.message(F.text.in_({"👥 Сотрудники", "👥 Кормандон"}))
async def mgmt_employees(message: Message, session: AsyncSession, _: Any) -> None:
    result = await session.execute(
        select(User)
        .options(joinedload(User.store))
        .where(User.is_active.is_(True))
        .order_by(User.role, User.name)
    )
    users = result.scalars().all()
    await message.answer(
        _("mgmt_empl_title"),
        parse_mode="HTML",
        reply_markup=employees_list_kb(users, _=_),
    )

@router.callback_query(F.data == "mgmt:employees")
async def mgmt_employees_callback(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    result = await session.execute(
        select(User)
        .options(joinedload(User.store))
        .where(User.is_active.is_(True))
        .order_by(User.role, User.name)
    )
    users = result.scalars().all()
    await callback.message.edit_text(
        _("mgmt_empl_title"),
        parse_mode="HTML",
        reply_markup=employees_list_kb(users, _=_),
    )
    await callback.answer()


# ─── ➕ Пригласить сотрудника (Invite Flow) ──────────────────────────


@router.callback_query(F.data == "mgmt:invite")
async def invite_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    # First step: Choose Role
    from app.bot.keyboards.inline import invite_role_kb
    await callback.message.edit_text(
        _("mgmt_invite_role_text"),
        parse_mode="HTML",
        reply_markup=invite_role_kb(_=_),
    )
    await state.set_state(InviteFlow.select_role)
    await callback.answer()


@router.callback_query(InviteFlow.select_role, F.data.startswith("invite:role:"))
async def invite_select_role(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    role_str = callback.data.split(":")[-1]
    await state.update_data(role=role_str)
    
    store_svc = StoreService(session)
    if role_str == "warehouse":
        # Only show the main warehouse
        wh_id = await store_svc.get_main_warehouse_id()
        if wh_id is None:
            await callback.message.edit_text(_("mgmt_invite_wh_not_found"))
            await state.clear()
            return
        
        main_wh = await session.get(Store, wh_id)
        stores = [main_wh]
        text = _("mgmt_invite_wh_only")
    else:
        # Show all active stores for Seller
        stores = await store_svc.list_active_stores()
        text = _("mgmt_invite_seller_store")

    from app.bot.keyboards.inline import invite_stores_kb
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=invite_stores_kb(stores, back_data="mgmt:invite", _=_),
    )
    await state.set_state(InviteFlow.select_store)
    await callback.answer()


@router.callback_query(InviteFlow.select_store, F.data.startswith("invite:store:"))
async def invite_select_store(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    store_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    role_str = data["role"]
    role = UserRole(role_str)

    invite_svc = InviteService(session)
    invite = await invite_svc.create_invite(role, store_id)
    await session.commit()

    store = await session.get(Store, store_id)
    role_name = {"seller": _("role_seller"), "warehouse": _("role_warehouse")}.get(
        role_str, role_str
    )

    await callback.message.edit_text(
        _("mgmt_invite_success", code=invite.code, store=store.name, role=role_name),
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


# ─── 📋 Должники ────────────────────────────────────────────────────


@router.message(F.text.in_({"📋 Должники", "📋 Қарздорҳо"}))
async def mgmt_debtors(message: Message, session: AsyncSession, _: Any) -> None:
    txn_svc = TransactionService(session)
    stores = await txn_svc.get_stores_with_debt()
    if not stores:
        await message.answer(_("mgmt_debtors_empty"))
        return

    text = _("mgmt_debtors_title") + "\n\n"
    total = Decimal("0")
    for s in stores:
        text += _("mgmt_debtor_item", name=s.name, debt=s.current_debt) + "\n"
        total += s.current_debt
    text += _("mgmt_debtors_total", total=total)

    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "mgmt:debtors")
async def mgmt_debtors_callback(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    txn_svc = TransactionService(session)
    stores = await txn_svc.get_stores_with_debt()
    if not stores:
        await callback.message.edit_text(_("mgmt_debtors_empty"))
        await callback.answer()
        return

    text = _("mgmt_debtors_title") + "\n\n"
    total = Decimal("0")
    for s in stores:
        text += _("mgmt_debtor_item", name=s.name, debt=s.current_debt) + "\n"
        total += s.current_debt
    text += _("mgmt_debtors_total", total=total)

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


# ─── 🏆 Рейтинг ─────────────────────────────────────────────────────


@router.message(F.text.in_({"🏆 Рейтинг", "🏆 Рейтинг"}))
async def mgmt_rating(message: Message, _: Any) -> None:
    from app.bot.keyboards.inline import rating_period_kb
    await message.answer(
        _("mgmt_rating_select_period"),
        parse_mode="HTML",
        reply_markup=rating_period_kb(_=_),
    )


@router.callback_query(F.data == "mgmt:rating")
async def mgmt_rating_callback(callback: CallbackQuery, _: Any) -> None:
    from app.bot.keyboards.inline import rating_period_kb
    await callback.message.edit_text(
        _("mgmt_rating_select_period"),
        parse_mode="HTML",
        reply_markup=rating_period_kb(_=_),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mgmt:rating:"))
async def mgmt_rating_by_period(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    from datetime import date, datetime, time, timedelta
    from app.services.analytics_service import AnalyticsService

    period = callback.data.split(":")[-1]
    today = date.today()
    
    if period == "today":
        start_date = datetime.combine(today, time.min)
        end_date = None
        period_text = _("period_today")
    elif period == "yesterday":
        yesterday = today - timedelta(days=1)
        start_date = datetime.combine(yesterday, time.min)
        end_date = datetime.combine(yesterday, time.max)
        period_text = _("period_yesterday")
    elif period == "week":
        start_date = datetime.combine(today - timedelta(days=7), time.min)
        end_date = None
        period_text = f"7 { _('unit_days') }"
    elif period == "month":
        start_date = datetime.combine(today - timedelta(days=30), time.min)
        end_date = None
        period_text = f"30 { _('unit_days') }"
    else:
        await callback.answer(_("error_label"))
        return

    analytics_svc = AnalyticsService(session)
    rows = await analytics_svc.get_store_rating(start_date, end_date)

    if not rows:
        from app.bot.keyboards.inline import rating_period_kb
        await callback.message.edit_text(
            _("rate_no_data"), 
            parse_mode="HTML",
            reply_markup=rating_period_kb(_=_)
        )
        await callback.answer()
        return

    text = _("rate_title", period=period_text) + "\n\n"
    for i, row in enumerate(rows, 1):
        name, total = row
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += _("mgmt_rating_item", medal=medal, name=name, total=total) + "\n"

    from app.bot.keyboards.inline import rating_period_kb
    await callback.message.edit_text(
        text, 
        parse_mode="HTML",
        reply_markup=rating_period_kb(_=_)
    )
    await callback.answer()
