"""Reply keyboards — persistent bottom menus for each role."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


# ─── Seller ───────────────────────────────────────────────────────────
SELLER_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📦 Заказать товар"),
            KeyboardButton(text="💼 Мои остатки"),
        ],
        [
            KeyboardButton(text="💰 Оформить продажу"),
            KeyboardButton(text="📊 Отчет за день"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)

# ─── Warehouse ────────────────────────────────────────────────────────
WAREHOUSE_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔔 Активные запросы"),
            KeyboardButton(text="📦 Остатки склада"),
        ],
        [
            KeyboardButton(text="🚚 История отгрузок"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)

# ─── Owner ────────────────────────────────────────────────────────────
OWNER_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📈 Дашборд за сегодня"),
            KeyboardButton(text="🏪 Рейтинг магазинов"),
        ],
        [
            KeyboardButton(text="💸 Начать сбор кассы"),
            KeyboardButton(text="📝 Список должников"),
        ],
        [
            KeyboardButton(text="🆕 Добавить товар"),
            KeyboardButton(text="📥 Пополнить склад"),
        ],
        [
            KeyboardButton(text="📦 Популярные товары"),
            KeyboardButton(text="⚙️ Настройки"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
)
