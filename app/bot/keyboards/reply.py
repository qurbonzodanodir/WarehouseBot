"""Reply keyboards — persistent bottom menus for each role."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


# ─── Seller ───────────────────────────────────────────────────────────
SELLER_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🖼 Витрина"),
            KeyboardButton(text="🛒 Заказ"),
        ],
        [
            KeyboardButton(text="📜 Продажи"),
            KeyboardButton(text="📊 Отчет"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)

# ─── Warehouse ────────────────────────────────────────────────────────
WAREHOUSE_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📥 Приход"),
            KeyboardButton(text="📋 Образцы"),
        ],
        [
            KeyboardButton(text="🔔 Запросы"),
            KeyboardButton(text="📦 Остатки"),
        ],
        [
            KeyboardButton(text="🚚 Отгрузки"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)

OWNER_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Дашборд"),
            KeyboardButton(text="💰 Инкассация"),
        ],
        [
            KeyboardButton(text="📦 Каталог"),
            KeyboardButton(text="⚙️ Управление"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)
