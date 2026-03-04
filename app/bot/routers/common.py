from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.reply import (
    OWNER_MENU,
    SELLER_MENU,
    WAREHOUSE_MENU,
)
from app.bot.states.states import RegistrationFlow
from app.core.config import settings
from app.models.enums import UserRole
from app.models.user import User
from app.services import invite_service

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
    message: Message, user: User | None, telegram_id: int,
    session: AsyncSession, state: FSMContext,
) -> None:
    """Greet registered user or prompt for invite code."""
    if user is not None:
        # Already registered → show menu
        keyboard = MENU_MAP.get(user.role, OWNER_MENU)
        greeting = GREETING.get(user.role, "👋 Главное меню")
        await message.answer(
            f"Привет, {user.name}!\n{greeting}",
            reply_markup=keyboard,
        )
        return

    # Not registered → check if this is the owner from .env
    if settings.owner_telegram_id and telegram_id == settings.owner_telegram_id:
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
            f"👑 Добро пожаловать, {full_name}!\n"
            f"Вы автоматически зарегистрированы как Владелец.\n\n"
            f"Нажмите /start чтобы открыть меню.",
        )
        return

    # Unknown user → ask for invite code
    await state.set_state(RegistrationFlow.enter_code)
    await message.answer(
        "🔒 Бот доступен только для авторизованных сотрудников.\n\n"
        "Введите код приглашения:"
    )


# ─── Invite code registration ───────────────────────────────────────


@router.message(RegistrationFlow.enter_code)
async def process_invite_code(
    message: Message, state: FSMContext, telegram_id: int,
    session: AsyncSession,
) -> None:
    """Validate the invite code and register the user."""
    code = message.text.strip().upper()

    # Look up the code via service
    invite = await invite_service.get_invite_by_code(session, code)

    if invite is None:
        await message.answer(
            "❌ Код недействителен или просрочен.\n"
            "Обратитесь к руководству за новым кодом.\n\n"
            "Попробуйте ввести код ещё раз:"
        )
        return

    # Register the user
    full_name = message.from_user.full_name or "Сотрудник"
    new_user = User(
        telegram_id=telegram_id,
        name=full_name,
        role=invite.role,
        store_id=invite.store_id,
        is_active=True,
    )
    session.add(new_user)
    await session.flush()  # get new_user.id

    # Mark code as used
    await invite_service.use_invite(session, invite, new_user.id)
    await session.commit()

    await state.clear()

    keyboard = MENU_MAP.get(invite.role, OWNER_MENU)
    greeting = GREETING.get(invite.role, "👋 Главное меню")
    store_name = invite.store.name if invite.store else "—"

    await message.answer(
        f"✅ Добро пожаловать, {full_name}!\n\n"
        f"Роль: {greeting}\n"
        f"Магазин: {store_name}\n\n"
        f"Ваше меню готово! 👇",
        reply_markup=keyboard,
    )


# ─── /switch_role (DEBUG only) ───────────────────────────────────────


@router.message(Command("switch_role"))
async def cmd_switch_role(
    message: Message, user: User | None, session: AsyncSession
) -> None:
    """Switch role for testing. Only works when DEBUG=true."""
    if not settings.debug:
        await message.answer("⛔ Эта команда доступна только в режиме отладки.")
        return

    if user is None:
        await message.answer("⛔ Вы не зарегистрированы.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "🔄 <b>Смена роли (DEBUG)</b>\n\n"
            "Использование:\n"
            "<code>/switch_role seller 6</code> — продавец\n"
            "<code>/switch_role warehouse 5</code> — складчик\n"
            "<code>/switch_role owner</code> — владелец\n\n"
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

    keyboard = MENU_MAP.get(new_role, OWNER_MENU)
    greeting = GREETING.get(new_role, "👋")
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
