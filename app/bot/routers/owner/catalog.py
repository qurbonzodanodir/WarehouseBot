from decimal import Decimal, InvalidOperation
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states.states import AddProductFlow
from app.models.product import Product

router = Router(name="owner.catalog")


async def _send_catalog_page(
    message_or_callback: Message | CallbackQuery, 
    products: list[Product], 
    page: int,
    _: Any
) -> None:
    from app.bot.keyboards.inline import get_page_slice, add_pagination_buttons
    limit = 20
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=_("cat_add_btn"), callback_data="catalog:add"))

    if not products:
        text = _("cat_empty")
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text, reply_markup=builder.as_markup())
        else:
            await message_or_callback.message.edit_text(text, reply_markup=builder.as_markup())
        return

    start, end = get_page_slice(len(products), page, limit)
    page_items = products[start:end]

    lines = [_("cat_title", page=page + 1)]
    for p in page_items:
        lines.append(_("catalog_item_detail", sku=p.sku, price=p.price))
        
    add_pagination_buttons(builder, len(products), page, limit, "catalog:page", _=_)
    
    text = "\n".join(lines)
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await message_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.message(F.text.in_({"📦 Каталог"}))
async def catalog_view(message: Message, session: AsyncSession, _: Any) -> None:
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()
    await _send_catalog_page(message, products, page=0, _=_)


@router.callback_query(F.data.startswith("catalog:page:"))
async def catalog_page_nav(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    page = int(callback.data.split(":")[-1])
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()
    await _send_catalog_page(callback, products, page, _=_)
    await callback.answer()



@router.callback_query(F.data == "catalog:add")
async def catalog_add_product(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.message.edit_text(
        _("cat_enter_sku"), parse_mode="HTML"
    )
    await state.set_state(AddProductFlow.enter_sku)
    await callback.answer()


@router.message(AddProductFlow.enter_sku)
async def add_product_sku(message: Message, state: FSMContext, _: Any) -> None:
    sku = message.text.strip().upper()
    await state.update_data(sku=sku)
    await message.answer(
        _("cat_enter_price", sku=sku),
        parse_mode="HTML",
    )
    await state.set_state(AddProductFlow.enter_price)


@router.message(AddProductFlow.enter_price)
async def add_product_price(
    message: Message, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    try:
        price = Decimal(message.text.strip())
        if price <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer(_("cat_invalid_price"))
        return

    data = await state.get_data()
    sku = data["sku"]

    existing = await session.execute(select(Product).where(Product.sku == sku))
    if existing.scalar_one_or_none():
        await message.answer(_("cat_exists", sku=sku))
        await state.clear()
        return

    product = Product(sku=sku, price=price, is_active=True)
    session.add(product)
    await session.commit()

    await message.answer(
        _("cat_success", sku=sku, amount=price),
        parse_mode="HTML",
    )
    await state.clear()

 
