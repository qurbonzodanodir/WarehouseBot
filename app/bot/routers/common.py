from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.reply import (
    OWNER_MENU,
    SELLER_MENU,
    WAREHOUSE_MENU,
)
from app.models.enums import UserRole
from app.models.user import User

router = Router(name="common")

MENU_MAP = {
    UserRole.SELLER: SELLER_MENU,
    UserRole.WAREHOUSE: WAREHOUSE_MENU,
    UserRole.OWNER: OWNER_MENU,
}

GREETING = {
    UserRole.SELLER: "🛒 Меню продавца",
    UserRole.WAREHOUSE: "🏭 Меню складчика",
    UserRole.OWNER: "👑 Меню владельца",
}


@router.message(CommandStart())
async def cmd_start(
    message: Message, user: User | None, telegram_id: int
) -> None:
    """Send a greeting with the role-specific keyboard, or registration info."""
    if user is None:
        await message.answer(
            f"⛔ Вы не зарегистрированы в системе.\n\n"
            f"Ваш Telegram ID: <code>{telegram_id}</code>\n\n"
            f"Передайте этот ID владельцу системы для регистрации.\n\n"
            f"Или, если вы владелец, используйте команду:\n"
            f"/register_owner",
            parse_mode="HTML",
        )
        return

    keyboard = MENU_MAP.get(user.role, OWNER_MENU)
    greeting = GREETING.get(user.role, "👋 Главное меню")
    await message.answer(
        f"Привет, {user.name}!\n{greeting}",
        reply_markup=keyboard,
    )


@router.message(Command("register_owner"))
async def cmd_register_owner(
    message: Message, user: User | None, telegram_id: int, session: AsyncSession
) -> None:
    """Self-register as owner (only if no owners exist yet)."""
    if user is not None:
        await message.answer("Вы уже зарегистрированы!")
        return

    # Check if any owner exists
    from sqlalchemy import select, func

    stmt = select(func.count()).select_from(User).where(
        User.role == UserRole.OWNER, User.is_active.is_(True)
    )
    result = await session.execute(stmt)
    owner_count = result.scalar()

    if owner_count > 0:
        await message.answer(
            "⛔ Владелец уже существует.\n"
            "Попросите его добавить вас в систему."
        )
        return

    # Register as owner
    full_name = message.from_user.full_name or "Owner"
    new_user = User(
        telegram_id=telegram_id,
        name=full_name,
        role=UserRole.OWNER,
        store_id=None,
        is_active=True,
    )
    session.add(new_user)
    await session.commit()

    await message.answer(
        f"✅ Вы зарегистрированы как Владелец!\n"
        f"Имя: {full_name}\n\n"
        f"Нажмите /start чтобы открыть меню.",
    )


@router.message(Command("add_user"))
async def cmd_add_user(
    message: Message, user: User | None, session: AsyncSession
) -> None:
    """
    Owner adds a new user. Usage:
    /add_user <telegram_id> <role> <store_id> <name>
    Example: /add_user 123456789 seller 6 Алишер
    """
    if user is None or user.role != UserRole.OWNER:
        await message.answer("⛔ Только владелец может добавлять сотрудников.")
        return

    parts = message.text.split(maxsplit=4)
    if len(parts) < 5:
        await message.answer(
            "Использование:\n"
            "<code>/add_user &lt;telegram_id&gt; &lt;role&gt; &lt;store_id&gt; &lt;имя&gt;</code>\n\n"
            "Роли: seller, warehouse, admin, owner\n\n"
            "Пример:\n"
            "<code>/add_user 123456789 seller 6 Алишер</code>",
            parse_mode="HTML",
        )
        return

    _, tg_id_str, role_str, store_id_str, name = parts

    try:
        tg_id = int(tg_id_str)
    except ValueError:
        await message.answer("❌ telegram_id должен быть числом.")
        return

    try:
        role = UserRole(role_str.lower())
    except ValueError:
        await message.answer(
            f"❌ Неизвестная роль: {role_str}\n"
            f"Допустимые: seller, warehouse, admin, owner"
        )
        return

    store_id = None
    if store_id_str != "0":
        try:
            store_id = int(store_id_str)
        except ValueError:
            await message.answer("❌ store_id должен быть числом (или 0 если без магазина).")
            return

    # Check if already exists
    from app.services.user_service import get_user_by_telegram_id

    existing = await get_user_by_telegram_id(session, tg_id)
    if existing:
        await message.answer(f"⚠️ Пользователь с TG ID {tg_id} уже существует.")
        return

    new_user = User(
        telegram_id=tg_id,
        name=name,
        role=role,
        store_id=store_id,
        is_active=True,
    )
    session.add(new_user)
    await session.commit()

    await message.answer(
        f"✅ Пользователь добавлен!\n"
        f"Имя: {name}\n"
        f"Роль: {role.value}\n"
        f"Магазин ID: {store_id or '—'}\n"
        f"TG ID: {tg_id}"
    )


@router.message(Command("switch_role"))
async def cmd_switch_role(
    message: Message, user: User | None, session: AsyncSession
) -> None:
    """
    Switch your own role for testing. Owner-only.
    /switch_role seller 6    — become seller at store 6
    /switch_role warehouse 5 — become warehouse worker at store 5
    /switch_role owner       — switch back to owner
    """
    if user is None:
        await message.answer("⛔ Вы не зарегистрированы.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "🔄 <b>Смена роли (для тестирования)</b>\n\n"
            "Использование:\n"
            "<code>/switch_role seller 6</code> — продавец Магазин №1\n"
            "<code>/switch_role warehouse 5</code> — складчик\n"
            "<code>/switch_role owner</code> — вернуться к владельцу\n\n"
            "Магазины: 5=Склад, 6=Магазин №1, 7=Магазин №2\n\n"
            f"Текущая роль: <b>{user.role.value}</b>",
            parse_mode="HTML",
        )
        return

    role_str = parts[1].lower()
    try:
        new_role = UserRole(role_str)
    except ValueError:
        await message.answer(
            f"❌ Неизвестная роль: {role_str}\n"
            f"Допустимые: seller, warehouse, owner"
        )
        return

    store_id = None
    if len(parts) >= 3 and parts[2] != "0":
        try:
            store_id = int(parts[2])
        except ValueError:
            await message.answer("❌ store_id должен быть числом.")
            return

    user.role = new_role
    user.store_id = store_id
    await session.commit()

    keyboard = MENU_MAP[new_role]
    greeting = GREETING[new_role]
    await message.answer(
        f"🔄 Роль изменена!\n{greeting}\n"
        f"Магазин ID: {store_id or '—'}",
        reply_markup=keyboard,
    )


@router.message(Command("my_role"))
async def cmd_my_role(
    message: Message, user: User | None
) -> None:
    """Show current role and store."""
    if user is None:
        await message.answer("⛔ Вы не зарегистрированы.")
        return
    store_name = user.store.name if user.store else "—"
    await message.answer(
        f"👤 <b>{user.name}</b>\n"
        f"Роль: {user.role.value}\n"
        f"Магазин: {store_name}",
        parse_mode="HTML",
    )
