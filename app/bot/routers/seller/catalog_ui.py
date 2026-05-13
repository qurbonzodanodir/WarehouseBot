from html import escape
from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from app.bot.keyboards.inline import add_pagination_buttons, get_page_slice


CATALOG_PAGE_LIMIT = 12


def clean_search_query(text: str) -> str:
    return text.strip().lower().replace(" ", "").replace("-", "")


def product_matches(product: Any, query: str) -> bool:
    clean_query = clean_search_query(query)
    return (
        clean_query in clean_search_query(str(getattr(product, "sku", "")))
        or clean_query in clean_search_query(str(getattr(product, "brand", "")))
    )


def _product_from_item(item: Any) -> Any:
    return getattr(item, "product", item)


def _quantity_from_item(item: Any) -> int | None:
    return getattr(item, "quantity", None)


def _clean_brand(brand: str | None, max_len: int = 12) -> str:
    value = (brand or "").strip()
    if not value or value.upper() == "UNKNOWN":
        return "-"
    return value[:max_len]


def _format_catalog_table(items: list[Any], _: Any) -> str:
    lines = [
        f"{_('stock_col_sku'):<9} {_('stock_col_brand'):<12} {_('stock_col_qty'):>3}",
        "-" * 28,
    ]
    for item in items:
        product = _product_from_item(item)
        quantity = _quantity_from_item(item)
        qty_text = "-" if quantity is None else str(quantity)
        sku = str(getattr(product, "sku", ""))[:9]
        brand = _clean_brand(getattr(product, "brand", None))
        lines.append(f"{sku:<9} {brand:<12} {qty_text:>3}")
    return "<pre>" + escape("\n".join(lines)) + "</pre>"


def catalog_message(title: str, items: list[Any], page: int, _: Any) -> str:
    total_pages = max(1, (len(items) + CATALOG_PAGE_LIMIT - 1) // CATALOG_PAGE_LIMIT)
    start, end = get_page_slice(len(items), page, CATALOG_PAGE_LIMIT)
    page_items = items[start:end]
    return "\n".join(
        [
            title,
            _("catalog_page", page=page + 1, total=total_pages),
            "",
            _format_catalog_table(page_items, _),
            "",
            _("catalog_hint"),
        ]
    )


def catalog_markup(
    items: list[Any],
    page: int,
    callback_prefix: str,
    item_callback_prefix: str,
    _: Any,
    selectable: bool = True,
) -> Any:
    builder = InlineKeyboardBuilder()
    start, end = get_page_slice(len(items), page, CATALOG_PAGE_LIMIT)
    page_items = items[start:end]

    if selectable:
        for item in page_items:
            product = _product_from_item(item)
            quantity = _quantity_from_item(item)
            brand = _clean_brand(getattr(product, "brand", None), max_len=10)
            qty_suffix = "" if quantity is None else f" • {quantity} {_('unit_pcs')}"
            builder.row(
                InlineKeyboardButton(
                    text=f"{getattr(product, 'sku', '')} • {brand}{qty_suffix}",
                    callback_data=f"{item_callback_prefix}:{product.id}",
                )
            )

    add_pagination_buttons(
        builder,
        len(items),
        page,
        CATALOG_PAGE_LIMIT,
        callback_prefix,
        _=_,
    )
    markup = builder.as_markup()
    return markup if markup.inline_keyboard else None


async def send_catalog_page(
    target: Message | CallbackQuery,
    title: str,
    items: list[Any],
    page: int,
    callback_prefix: str,
    item_callback_prefix: str,
    _: Any,
    selectable: bool = True,
) -> None:
    text = catalog_message(title, items, page, _)
    markup = catalog_markup(items, page, callback_prefix, item_callback_prefix, _, selectable=selectable)
    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=markup)
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=markup)


def product_card(product: Any, _: Any, qty: int | None = None) -> str:
    lines = [
        f"📦 <b>{escape(str(getattr(product, 'sku', '')))}</b>",
        f"{_('stock_col_brand')}: {escape(_clean_brand(getattr(product, 'brand', None), max_len=24))}",
    ]
    if qty is not None:
        lines.append(f"{_('stock_col_qty')}: {qty} {_('unit_pcs')}")
    return "\n".join(lines)
