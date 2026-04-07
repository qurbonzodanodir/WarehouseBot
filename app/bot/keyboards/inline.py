import math

from typing import Any
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder



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
    _: Any,
) -> None:
    """Add pagination row to an inline keyboard builder."""
    total_pages = math.ceil(total_items / limit)
    if total_pages <= 1:
        return

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text=_("btn_prev"),
                callback_data=f"{callback_prefix}:{page - 1}",
            )
        )
    
    nav_buttons.append(
        InlineKeyboardButton(
            text=_("btn_page", current=page + 1, total=total_pages),
            callback_data="ignore",
        )
    )

    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text=_("btn_next"),
                callback_data=f"{callback_prefix}:{page + 1}",
            )
        )
        
    builder.row(*nav_buttons)



def partial_approval_kb(order_id: int, _: Any) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_accept"),
            callback_data=f"order:partial_accept:{order_id}",
        ),
        InlineKeyboardButton(
            text=_("btn_reject"),
            callback_data=f"order:partial_reject:{order_id}",
        ),
    )
    return builder.as_markup()



def order_action_kb(order_id: int, _: Any) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_dispatch"),
            callback_data=f"order:dispatch:{order_id}",
        ),
        InlineKeyboardButton(
            text=_("btn_cancel_order"),
            callback_data=f"order:reject:{order_id}",
        ),
    )
    return builder.as_markup()

def cart_action_kb(_: Any) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_("btn_cart_add_more"), callback_data="cart:add_more"),
        InlineKeyboardButton(text=_("btn_cart_send"), callback_data="cart:send"),
    )
    builder.row(
        InlineKeyboardButton(text=_("btn_cart_clear"), callback_data="cart:clear"),
    )
    return builder.as_markup()

def batch_order_action_kb(batch_id: str, _: Any) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_accept_batch"),
            callback_data=f"order:approve_batch:{batch_id}",
        ),
        InlineKeyboardButton(
            text=_("btn_reject_batch"),
            callback_data=f"order:reject_batch:{batch_id}",
        ),
    )
    return builder.as_markup()

def batch_partial_proposal_kb(batch_id: str, _: Any) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_accept_partial_batch"),
            callback_data=f"order:partial_accept_batch:{batch_id}",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text=_("btn_reject_partial_batch"),
            callback_data=f"order:partial_reject_batch:{batch_id}",
        ),
    )
    return builder.as_markup()


def batch_delivery_confirm_kb(batch_id: str, _: Any) -> InlineKeyboardMarkup:
    """Single accept button for seller when a batch delivery arrives."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_accept_batch"),
            callback_data=f"order:batch_accept:{batch_id}",
        ),
    )
    return builder.as_markup()



def delivery_confirm_kb(order_id: int, quantity: int, _: Any) -> InlineKeyboardMarkup:
    """Single accept button for seller when courier arrives."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_confirm_receive", qty=quantity),
            callback_data=f"order:accept:{order_id}",
        ),
    )
    return builder.as_markup()


def delivery_accepted_kb(order_id: int, _: Any) -> InlineKeyboardMarkup:
    """After seller accepts delivery — sell or return."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_sold"),
            callback_data=f"order:sold:{order_id}",
        ),
        InlineKeyboardButton(
            text=_("btn_return_damaged"),
            callback_data=f"order:return:{order_id}",
        ),
    )
    return builder.as_markup()

def batch_delivery_accepted_kb(batch_id: str, _: Any) -> InlineKeyboardMarkup:
    """After seller accepts batch delivery — sell or return the entire batch."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_sold"),
            callback_data=f"order:sell_batch:{batch_id}",
        ),
        InlineKeyboardButton(
            text=_("btn_return_damaged"),
            callback_data=f"order:return_batch:{batch_id}",
        ),
    )
    return builder.as_markup()

def warehouse_return_kb(order_id: int, _: Any) -> InlineKeyboardMarkup:
    """Keyboard for warehouse to approve or reject a return from a store."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_approve_return"),
            callback_data=f"order:approve_return:{order_id}",
        ),
        InlineKeyboardButton(
            text=_("btn_reject_return"),
            callback_data=f"order:reject_return:{order_id}",
        ),
    )
    return builder.as_markup()


def display_receive_kb(order_id: int, _: Any) -> InlineKeyboardMarkup:
    """Keyboard for seller to confirm receiving display samples."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_("btn_received"),
            callback_data=f"display:receive:{order_id}",
        ),
        InlineKeyboardButton(
            text=_("btn_not_received"),
            callback_data=f"display:reject:{order_id}",
        ),
    )
    return builder.as_markup()



def product_select_kb(
    inventory_items: list,
    page: int = 0,
    limit: int = 10,
    callback_prefix: str = "sell:page",
    item_callback_prefix: str = "sell:product",
    _: Any = None,
) -> InlineKeyboardMarkup:
    """List store inventory as buttons for the seller to pick a product, with pagination."""
    builder = InlineKeyboardBuilder()
    
    start, end = get_page_slice(len(inventory_items), page, limit)
    page_items = inventory_items[start:end]
    
    for inv in page_items:
        builder.row(
            InlineKeyboardButton(
                text=f"{inv.product.sku} ({_('stock_qty_suffix', qty=inv.quantity)})",
                callback_data=f"{item_callback_prefix}:{inv.product_id}",
            )
        )
        
    add_pagination_buttons(builder, len(inventory_items), page, limit, callback_prefix, _=_)
    return builder.as_markup()







def catalog_kb(
    products: list,
    page: int = 0,
    limit: int = 10,
    callback_prefix: str = "order:page",
    item_callback_prefix: str = "order:select",
    _: Any = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    start, end = get_page_slice(len(products), page, limit)
    page_items = products[start:end]
    
    for p in page_items:
        builder.row(
            InlineKeyboardButton(
                text=f"{p.sku} ({_('price_suffix', price=p.price)})",
                callback_data=f"{item_callback_prefix}:{p.id}",
            )
        )
        
    add_pagination_buttons(builder, len(products), page, limit, callback_prefix, _=_)
    return builder.as_markup()





def language_selection_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang:ru"),
        InlineKeyboardButton(text="Тоҷикӣ 🇹🇯", callback_data="lang:tg"),
    )
    return builder.as_markup()
