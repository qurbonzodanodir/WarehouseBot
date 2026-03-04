from decimal import Decimal, InvalidOperation

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
    page: int
) -> None:
    from app.bot.keyboards.inline import get_page_slice, add_pagination_buttons
    limit = 20
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить товар", callback_data="catalog:add"))

    if not products:
        text = "📦 Каталог пуст.\n\nНажмите кнопку ниже, чтобы добавить первый товар."
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text, reply_markup=builder.as_markup())
        else:
            await message_or_callback.message.edit_text(text, reply_markup=builder.as_markup())
        return

    start, end = get_page_slice(len(products), page, limit)
    page_items = products[start:end]

    lines = [f"📦 <b>Каталог товаров (стр {page + 1}):</b>\n"]
    for p in page_items:
        lines.append(f"• <code>{p.sku}</code> — {p.name} | {p.price} сом")
        
    add_pagination_buttons(builder, len(products), page, limit, "catalog:page")
    
    text = "\n".join(lines)
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        await message_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())


@router.message(F.text == "📦 Каталог")
async def catalog_view(message: Message, session: AsyncSession) -> None:
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()
    await _send_catalog_page(message, products, page=0)


@router.callback_query(F.data.startswith("catalog:page:"))
async def catalog_page_nav(callback: CallbackQuery, session: AsyncSession) -> None:
    page = int(callback.data.split(":")[-1])
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()
    await _send_catalog_page(callback, products, page)
    await callback.answer()



@router.callback_query(F.data == "catalog:add")
async def catalog_add_product(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "Введите <b>артикул (SKU)</b> нового товара:", parse_mode="HTML"
    )
    await state.set_state(AddProductFlow.enter_sku)
    await callback.answer()


@router.message(AddProductFlow.enter_sku)
async def add_product_sku(message: Message, state: FSMContext) -> None:
    sku = message.text.strip().upper()
    await state.update_data(sku=sku)
    await message.answer(
        f"SKU: <code>{sku}</code>\n\nТеперь введите <b>название</b> товара:",
        parse_mode="HTML",
    )
    await state.set_state(AddProductFlow.enter_name)


@router.message(AddProductFlow.enter_name)
async def add_product_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    await state.update_data(name=name)
    await message.answer(
        f"Название: {name}\n\nТеперь введите <b>цену</b> (сом):",
        parse_mode="HTML",
    )
    await state.set_state(AddProductFlow.enter_price)


@router.message(AddProductFlow.enter_price)
async def add_product_price(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        price = Decimal(message.text.strip())
        if price <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer("❌ Введите корректную положительную цену.")
        return

    data = await state.get_data()
    sku = data["sku"]
    name = data["name"]

    existing = await session.execute(select(Product).where(Product.sku == sku))
    if existing.scalar_one_or_none():
        await message.answer(f"⚠️ Товар с SKU {sku} уже существует.")
        await state.clear()
        return

    product = Product(sku=sku, name=name, price=price, is_active=True)
    session.add(product)
    await session.commit()

    await message.answer(
        f"✅ Товар добавлен!\n\n"
        f"SKU: <code>{sku}</code>\n"
        f"Название: {name}\n"
        f"Цена: {price} сом\n\n"
        f"Чтобы добавить на склад, нажмите 📥 Пополнить склад",
        parse_mode="HTML",
    )
    await state.clear()
