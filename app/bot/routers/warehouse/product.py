from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.states.states import ReceiveStockFlow
from app.models.product import Product
from app.bot.routers.warehouse.receive import WH_MENU_TEXTS
from typing import Any
router = Router(name="warehouse.product")


@router.message(F.text.in_({"➕ Добавить товар", "➕ Иловаи мол", "➕ Иловаи маҳсулот"}))
async def btn_add_product(message: Message, state: FSMContext, _: Any) -> None:
    """Entry point from 'Ещё 🔽' -> '➕ Добавить товар'."""
    await message.answer(
        _("product_create_title"),
        parse_mode="HTML"
    )
    await state.set_state(ReceiveStockFlow.new_product_sku)


@router.callback_query(
    ReceiveStockFlow.select_product, F.data == "receive:create_new"
)
async def receive_create_new_product(
    callback: CallbackQuery, state: FSMContext, _: Any
) -> None:
    """Entry point from inline search when a product is not found."""
    await callback.message.edit_text(
        _("product_create_title"),
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.new_product_sku)
    await callback.answer()


@router.message(ReceiveStockFlow.new_product_sku, F.text)
async def receive_new_product_sku(
    message: Message, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    if message.text.strip() in WH_MENU_TEXTS:
        await state.clear()
        return

    sku = message.text.strip().upper()

    # Check if SKU already exists
    result = await session.execute(
        select(Product).where(Product.sku == sku)
    )
    existing = result.scalar_one_or_none()
    if existing:
        await state.update_data(
            product_id=existing.id,
            product_sku=existing.sku,
        )
        await message.answer(
            _("product_sku_already_exists", sku=existing.sku),
            parse_mode="HTML",
        )
        await state.set_state(ReceiveStockFlow.enter_quantity)
        return

    await state.update_data(new_sku=sku)
    await message.answer(
        _("product_enter_price", sku=sku),
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.new_product_price)


@router.message(ReceiveStockFlow.new_product_price, F.text)
async def receive_new_product_price(
    message: Message, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    if message.text.strip() in WH_MENU_TEXTS:
        await state.clear()
        return

    text = message.text.strip().replace(",", ".")
    try:
        price = float(text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer(_("invalid_price"))
        return

    data = await state.get_data()
    sku = data["new_sku"]

    # Create the product
    product = Product(sku=sku, price=price, is_active=True)
    session.add(product)
    await session.commit()

    await state.update_data(
        product_id=product.id,
        product_sku=product.sku,
    )
    await message.answer(
        _("product_create_success", sku=sku, price=price),
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.enter_quantity)
