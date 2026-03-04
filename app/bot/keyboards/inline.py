import math

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.order import Order
from app.models.store import Store


def get_page_slice(total_items: int, page: int, limit: int) -> tuple[int, int]:
    """Calculate start and end indices for a page."""
    start = page * limit
    end = start + limit
    return start, min(end, total_items)


def add_pagination_buttons(
    builder: InlineKeyboardBuilder,
    total_items: int,
    page: int,
    limit: int,
    callback_prefix: str,
) -> None:
    """Add pagination row to an inline keyboard builder."""
    total_pages = math.ceil(total_items / limit)
    if total_pages <= 1:
        return

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"{callback_prefix}:{page - 1}",
            )
        )
    
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"Стр {page + 1}/{total_pages}",
            callback_data="ignore",
        )
    )

    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=f"{callback_prefix}:{page + 1}",
            )
        )
        
    builder.row(*nav_buttons)



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
    """Single accept button for seller when courier arrives."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"✅ Принял {quantity} шт",
            callback_data=f"order:accept:{order_id}",
        ),
    )
    return builder.as_markup()


def delivery_accepted_kb(order_id: int) -> InlineKeyboardMarkup:
    """After seller accepts delivery — sell or return."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="💰 Продал",
            callback_data=f"order:sold:{order_id}",
        ),
        InlineKeyboardButton(
            text="↩️ Брак/Возврат",
            callback_data=f"order:return:{order_id}",
        ),
    )
    return builder.as_markup()



def product_select_kb(
    inventory_items: list,
    page: int = 0,
    limit: int = 10,
    callback_prefix: str = "sell:page",
    item_callback_prefix: str = "sell:product",
) -> InlineKeyboardMarkup:
    """List store inventory as buttons for the seller to pick a product, with pagination."""
    builder = InlineKeyboardBuilder()
    
    start, end = get_page_slice(len(inventory_items), page, limit)
    page_items = inventory_items[start:end]
    
    for inv in page_items:
        builder.row(
            InlineKeyboardButton(
                text=f"{inv.product.name} ({inv.quantity} шт)",
                callback_data=f"{item_callback_prefix}:{inv.product_id}",
            )
        )
        
    add_pagination_buttons(builder, len(inventory_items), page, limit, callback_prefix)
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



def catalog_kb(
    products: list,
    page: int = 0,
    limit: int = 10,
    callback_prefix: str = "order:page",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    start, end = get_page_slice(len(products), page, limit)
    page_items = products[start:end]
    
    for p in page_items:
        builder.row(
            InlineKeyboardButton(
                text=f"{p.sku} — {p.name} ({p.price} сом)",
                callback_data=f"order:select:{p.id}",
            )
        )
        
    add_pagination_buttons(builder, len(products), page, limit, callback_prefix)
    return builder.as_markup()




def management_menu_kb() -> InlineKeyboardMarkup:
    """Main management inline menu."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏢 Магазины", callback_data="mgmt:stores"),
        InlineKeyboardButton(text="👥 Сотрудники", callback_data="mgmt:employees"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Должники", callback_data="mgmt:debtors"),
        InlineKeyboardButton(text="🏆 Рейтинг", callback_data="mgmt:rating"),
    )
    return builder.as_markup()


def stores_list_kb(stores: list[Store]) -> InlineKeyboardMarkup:
    """List stores with 'Add store' button."""
    builder = InlineKeyboardBuilder()
    for store in stores:
        builder.row(
            InlineKeyboardButton(
                text=f"🏢 {store.name} — {store.address}",
                callback_data=f"mgmt:store:{store.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить магазин", callback_data="mgmt:add_store"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="mgmt:back"),
    )
    return builder.as_markup()


def employees_list_kb(users: list) -> InlineKeyboardMarkup:
    """List employees with 'Invite' button."""
    builder = InlineKeyboardBuilder()
    for u in users:
        role_emoji = {"seller": "🛒", "warehouse": "🏭", "owner": "👑"}.get(u.role.value, "👤")
        store_name = u.store.name if u.store else "—"
        builder.row(
            InlineKeyboardButton(
                text=f"{role_emoji} {u.name} — {store_name}",
                callback_data=f"mgmt:employee:{u.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Пригласить сотрудника", callback_data="mgmt:invite"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="mgmt:back"),
    )
    return builder.as_markup()


def invite_stores_kb(stores: list[Store]) -> InlineKeyboardMarkup:
    """Pick store for invite code."""
    builder = InlineKeyboardBuilder()
    for store in stores:
        builder.row(
            InlineKeyboardButton(
                text=f"🏢 {store.name}",
                callback_data=f"invite:store:{store.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Отмена", callback_data="mgmt:back"),
    )
    return builder.as_markup()


def invite_role_kb() -> InlineKeyboardMarkup:
    """Pick role for invite code."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🛒 Продавец", callback_data="invite:role:seller"),
        InlineKeyboardButton(text="🏭 Складщик", callback_data="invite:role:warehouse"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Отмена", callback_data="mgmt:back"),
    )
    return builder.as_markup()
