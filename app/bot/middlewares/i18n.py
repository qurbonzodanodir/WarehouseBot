from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.core.i18n import Translator
from app.models.user import User

class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: User | None = data.get("user")
        lang = user.language_code if user else "ru"
        
        # Inject translator as _ to be accessible in all handlers
        data["_"] = Translator(lang)
        
        return await handler(event, data)
