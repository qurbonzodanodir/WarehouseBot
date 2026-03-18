from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import reply
from app.bot.states.states import RegistrationFlow
from app.core.config import settings
from app.models.enums import UserRole
from app.models.user import User
from app.services import InviteService

router = Router(name="common")

# Maps roles to the functions that generate their menus
MENU_MAP = {
    UserRole.SELLER: reply.get_seller_menu,
    UserRole.WAREHOUSE: reply.get_warehouse_menu,
    UserRole.OWNER: reply.get_owner_menu,
}

# Maps roles to translation keys
GREETING_KEYS = {
    UserRole.SELLER: "menu_seller",
    UserRole.WAREHOUSE: "menu_warehouse",
    UserRole.OWNER: "menu_owner",
}




@router.message(CommandStart())
async def cmd_start(
    message: Message, user: User | None, telegram_id: int,
    session: AsyncSession, state: FSMContext, _: Any,
) -> None:
    """Greet registered user or prompt for invite code."""
    if user is not None:
        # Already registered → show menu
        menu_func = MENU_MAP.get(user.role, reply.get_owner_menu)
        greeting_key = GREETING_KEYS.get(user.role, "👋")
        await message.answer(
            _("welcome", name=user.name, greeting=_(greeting_key)),
            reply_markup=menu_func(_),
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
            language_code="ru",
        )
        session.add(new_user)
        await session.commit()

        await message.answer(
            _("welcome_owner", name=full_name),
        )
        return

    # Unknown user → ask for invite code
    await state.set_state(RegistrationFlow.enter_code)
    await message.answer(_("auth_required"))


# ─── Invite code registration ───────────────────────────────────────


@router.message(RegistrationFlow.enter_code)
async def process_invite_code(
    message: Message, state: FSMContext, telegram_id: int,
    session: AsyncSession, _: Any,
) -> None:
    """Validate the invite code and register the user."""
    code = message.text.strip().upper()

    # Look up the code via service
    invite_svc = InviteService(session)
    invite = await invite_svc.get_invite_by_code(code)

    if invite is None:
        await message.answer(_("invalid_code"))
        return

    # Register or reactivate the user
    full_name = message.from_user.full_name or _("unknown")
    
    # Check if user already exists (e.g. was deleted/inactive)
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        existing_user.name = full_name
        existing_user.role = invite.role
        existing_user.store_id = invite.store_id
        existing_user.is_active = True
        user_for_invite = existing_user
    else:
        new_user = User(
            telegram_id=telegram_id,
            name=full_name,
            role=invite.role,
            store_id=invite.store_id,
            is_active=True,
            language_code="ru",
        )
        session.add(new_user)
        user_for_invite = new_user
    
    await session.flush()  # get ID if new

    # Mark code as used
    await invite_svc.use_invite(invite, user_for_invite.id)
    await session.commit()

    await state.clear()

    menu_func = MENU_MAP.get(invite.role, reply.get_owner_menu)
    greeting_key = GREETING_KEYS.get(invite.role, "👋")
    store_name = invite.store.name if invite.store else "—"

    await message.answer(
        _("welcome", name=full_name, greeting=_(greeting_key)) + f"\n" + _("store_label") + f": {store_name}",
        reply_markup=menu_func(_),
    )


# ─── Language Switching ──────────────────────────────────────────────

@router.message(F.text.in_({"🌐 Язык / Забон", "🌐 Забон / Язык"}))
async def cmd_language(message: Message, _: Any) -> None:
    """Show language selection keyboard."""
    from app.bot.keyboards.inline import language_selection_kb
    await message.answer(
        _("select_language"),
        reply_markup=language_selection_kb(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: Any, user: User, session: AsyncSession, _: Any) -> None:
    """Update user language."""
    from app.core.i18n import Translator
    lang = callback.data.split(":")[1]
    user.language_code = lang
    await session.commit()
    
    _ = Translator(lang)
    menu_func = MENU_MAP.get(user.role, reply.get_owner_menu)
    
    await callback.message.answer(
        _("lang_changed"),
        reply_markup=menu_func(_),
    )
    await callback.answer()


# ─── /switch_role (DEBUG only) ───────────────────────────────────────


@router.message(Command("switch_role"))
async def cmd_switch_role(
    message: Message, user: User | None, session: AsyncSession, _: Any
) -> None:
    """Switch role for testing. Only works when DEBUG=true."""
    if not settings.debug:
        await message.answer(_("debug_mode_only"))
        return

    if user is None:
        await message.answer(_("auth_not_registered"))
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            _("switch_role_usage", role=user.role.value),
            parse_mode="HTML",
        )
        return

    role_str = parts[1].lower()
    try:
        new_role = UserRole(role_str)
    except ValueError:
        await message.answer(
            _("unknown_role", role=role_str)
        )
        return

    store_id = None
    if len(parts) >= 3 and parts[2] != "0":
        try:
            store_id = int(parts[2])
        except ValueError:
            await message.answer(_("invalid_store_id"))
            return

    user.role = new_role
    user.store_id = store_id
    await session.commit()

    menu_func = MENU_MAP.get(new_role, reply.get_owner_menu)
    greeting_key = GREETING_KEYS.get(new_role, "👋")
    await message.answer(
        _("role_changed", greeting=_(greeting_key), store_id=store_id or "—"),
        reply_markup=menu_func(_),
    )




@router.message(Command("my_role"))
async def cmd_my_role(
    message: Message, user: User | None, _: Any
) -> None:
    """Show current role and store."""
    if user is None:
        await message.answer(_("auth_not_registered"))
        return
    store_name = user.store.name if user.store else "—"
    await message.answer(
        _("my_role_info", name=user.name, role=user.role.value, store=store_name),
        parse_mode="HTML",
    )
