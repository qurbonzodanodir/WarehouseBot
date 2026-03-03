from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.order import Order
from app.models.store import Store



def order_action_kb(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Отправить курьера",
            callback_data=f"order:dispatch:{order_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отказать",
            callback_data=f"order:reject:{order_id}",
        ),
    )
    return builder.as_markup()



def delivery_confirm_kb(order_id: int, quantity: int) -> InlineKeyboardMarkup:
    """Buttons a seller sees when a courier arrives."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"✅ Принять {quantity} шт",
            callback_data=f"order:accept:{order_id}",
        ),
        InlineKeyboardButton(
            text="❌ Брак/Недовоз",
            callback_data=f"order:reject:{order_id}",
        ),
    )
    return builder.as_markup()



def product_select_kb(
    inventory_items: list,
) -> InlineKeyboardMarkup:
    """List store inventory as buttons for the seller to pick a product."""
    builder = InlineKeyboardBuilder()
    for inv in inventory_items:
        builder.row(
            InlineKeyboardButton(
                text=f"{inv.product.name} ({inv.quantity} шт)",
                callback_data=f"sell:product:{inv.product_id}",
            )
        )
    return builder.as_markup()



def stores_debt_kb(stores: list[Store]) -> InlineKeyboardMarkup:
    """List stores with debt for the admin to pick from."""
    builder = InlineKeyboardBuilder()
    for store in stores:
        builder.row(
            InlineKeyboardButton(
                text=f"🏪 {store.name} — {store.current_debt} сом",
                callback_data=f"collect:store:{store.id}",
            )
        )
    return builder.as_markup()


def collection_amount_kb(
    store_id: int, debt: float
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"✅ Вся сумма ({debt} сом)",
            callback_data=f"collect:full:{store_id}",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Ввести другую сумму",
            callback_data=f"collect:partial:{store_id}",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отказ от сдачи",
            callback_data=f"collect:skip:{store_id}",
        ),
    )
    return builder.as_markup()



def catalog_kb(products: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in products:
        builder.row(
            InlineKeyboardButton(
                text=f"{p.sku} — {p.name} ({p.price} сом)",
                callback_data=f"order:select:{p.id}",
            )
        )
    return builder.as_markup()
