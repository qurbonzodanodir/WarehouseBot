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
        if user.role == UserRole.OWNER:
            # Owner → redirect to web dashboard
            await message.answer(
                _("owner_use_web"),
                parse_mode="HTML",
            )
            return

        # Seller/Warehouse → show menu
        menu_func = MENU_MAP.get(user.role, reply.get_seller_menu)
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

    # Unknown user → prompt for invite code
    await message.answer(_("auth_enter_code"))
    await state.set_state(RegistrationFlow.enter_code)




# ─── /code — enter invite code manually ──────────────────────────────


@router.message(Command("code"))
async def cmd_code(
    message: Message, user: User | None, state: FSMContext, _: Any,
) -> None:
    """Start invite code registration flow."""
    if user is not None:
        menu_func = MENU_MAP.get(user.role)
        greeting_key = GREETING_KEYS.get(user.role, "👋")
        if menu_func:
            await message.answer(
                _("welcome", name=user.name, greeting=_(greeting_key)),
                reply_markup=menu_func(_),
            )
        else:
            await message.answer(_("owner_use_web"), parse_mode="HTML")
        return
    await state.clear()
    await state.set_state(RegistrationFlow.enter_code)
    await message.answer(_("auth_enter_code"))


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

    menu_func = MENU_MAP.get(invite.role)
    greeting_key = GREETING_KEYS.get(invite.role, "👋")
    store_name = invite.store.name if invite.store else "—"

    text = _("welcome", name=full_name, greeting=_(greeting_key)) + "\n" + _("store_label") + f": {store_name}"
    if menu_func:
        await message.answer(text, reply_markup=menu_func(_))
    else:
        await message.answer(text + "\n\n" + _("owner_use_web"), parse_mode="HTML")


# ─── Language Switching ──────────────────────────────────────────────

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: Any) -> None:
    await callback.answer()


@router.message(F.text.in_({"🌐 Язык / Забон", "🌐 Забон / Язык"}))
async def cmd_language(message: Message, _: Any) -> None:
    """Show language selection keyboard."""
    from app.bot.keyboards.inline import language_selection_kb
    await message.answer(
        _("select_language"),
        reply_markup=language_selection_kb(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: Any, user: User | None, session: AsyncSession, _: Any) -> None:
    """Update user language."""
    from app.core.i18n import Translator
    lang = callback.data.split(":")[1]
    if user is None:
        await callback.answer(_("auth_enter_code"), show_alert=True)
        return
    user.language_code = lang
    _ = Translator(lang)
    session.add(user)
    await session.commit()
    
    menu_func = MENU_MAP.get(user.role)
    if menu_func:
        await callback.message.answer(
            _("lang_changed"),
            reply_markup=menu_func(_),
        )
    else:
        from aiogram.types import ReplyKeyboardRemove
        await callback.message.answer(
            _("lang_changed"),
            reply_markup=ReplyKeyboardRemove(),
        )
    await callback.answer()
