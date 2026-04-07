from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards import reply

router = Router(name="seller.common")

MENU_TEXTS = {
    "🖼 Витрина", "🖼 Рафи фурӯш",
    "🛒 Заказ", "🛒 Дархост",
    "💳 Продажа", "💳 Фурӯш",
    "📜 Продажи", "📜 Фурӯшҳо",
    "📊 Отчет", "📊 Ҳисобот",
    "↩️ Сделать возврат", "↩️ Бозгашти мол",
    "Ещё 🔽", "Боз 🔽", 
    "🔙 Назад", "🔙 Ба қафо",
}


@router.message(F.text.in_({"Ещё 🔽", "Боз 🔽"}))
async def show_more_menu(message: Message, state: FSMContext, _: Any) -> None:
    await state.clear()
    await message.answer(_("menu_seller_more"), reply_markup=reply.get_seller_more_menu(_))


@router.message(F.text.in_({"🔙 Назад", "🔙 Ба қафо"}))
async def back_to_main_menu(message: Message, state: FSMContext, _: Any) -> None:
    await state.clear()
    await message.answer(_("menu_main"), reply_markup=reply.get_seller_menu(_))
