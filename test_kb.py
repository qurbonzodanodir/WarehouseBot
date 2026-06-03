from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.bot.keyboards.inline import delivery_accepted_kb, batch_delivery_accepted_kb

def mock_gettext(key, **kwargs):
    return key

print(delivery_accepted_kb(123, mock_gettext).model_dump_json(indent=2))
print(batch_delivery_accepted_kb("batch_123", mock_gettext).model_dump_json(indent=2))
