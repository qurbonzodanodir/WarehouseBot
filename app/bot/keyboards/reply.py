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
            KeyboardButton(text="Ещё 🔽"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)

SELLER_MORE_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Отчет"),
            KeyboardButton(text="↩️ Сделать возврат"),
        ],
        [
            KeyboardButton(text="🔙 Назад"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Дополнительные опции",
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
            KeyboardButton(text="Ещё 🔽"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)

WAREHOUSE_MORE_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🚚 Отгрузки"),
            KeyboardButton(text="➕ Добавить товар"),
        ],
        [
            KeyboardButton(text="🔙 Назад"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Дополнительные опции",
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
