from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states.states import ReceiveStockFlow
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.user import User

router = Router(name="warehouse.receive")

# Menu texts that should NOT be treated as search queries
WH_MENU_TEXTS = {
    "📥 Приход", "📋 Образцы", "🔔 Запросы", "📦 Остатки",
    "🚚 Отгрузки", "Ещё 🔽", "🔙 Назад", "➕ Добавить товар",
}


@router.message(F.text == "➕ Добавить товар")
async def btn_add_product(
    message: Message, state: FSMContext
) -> None:
    await state.clear()
    await message.answer(
        "📝 <b>Создание нового товара</b>\n\n"
        "Введите артикул (SKU) нового товара:",
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.new_product_sku)


@router.message(F.text == "📥 Приход")
async def btn_receive_stock(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()

    from app.bot.keyboards.inline import catalog_kb

    if not products:
        await message.answer(
            "📭 Каталог товаров пуст.\n\n"
            "Введите артикул (SKU) нового товара, чтобы добавить его прямо сейчас:",
            parse_mode="HTML",
        )
        await state.set_state(ReceiveStockFlow.new_product_sku)
        return

    await message.answer(
        "🔎 <b>Приход товара</b>\n\n"
        "Напишите артикул (SKU) или название товара в чат.\n"
        "Либо выберите из каталога ниже:",
        parse_mode="HTML",
        reply_markup=catalog_kb(products, page=0, callback_prefix="receive:page"),
    )
    await state.set_state(ReceiveStockFlow.select_product)


@router.message(ReceiveStockFlow.select_product, F.text)
async def receive_search_product(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if message.text.strip() in WH_MENU_TEXTS:
        await state.clear()
        return

    from app.services.product_service import search_catalog
    product, matches = await search_catalog(session, message.text)

    if product:
        # Exact match
        await state.update_data(product_id=product.id, product_name=product.name, product_sku=product.sku)
        await message.answer(
            f"📦 <b>{product.sku}</b> — {product.name}\n\n"
            f"Введите количество (сколько пришло):",
            parse_mode="HTML",
        )
        await state.set_state(ReceiveStockFlow.enter_quantity)
        return

    if matches:
        from app.bot.keyboards.inline import catalog_kb
        await message.answer(
            "Найдено по вашему запросу. Выберите нужный товар:",
            reply_markup=catalog_kb(matches, page=0, callback_prefix="receive:page")
        )
        return

    # Not found — offer to create
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➕ Создать новый товар",
            callback_data="receive:create_new"
        )
    )
    await message.answer(
        f"❌ Товар <b>{message.text.strip()}</b> не найден в каталоге.\n\n"
        "Хотите добавить новый товар?",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.update_data(pending_sku=message.text.strip().upper())


# ─── Create new product inline ───────────────────────────────────────

@router.callback_query(
    ReceiveStockFlow.select_product, F.data == "receive:create_new"
)
async def receive_create_new_product(
    callback: CallbackQuery, state: FSMContext
) -> None:
    data = await state.get_data()
    pending_sku = data.get("pending_sku", "")

    if pending_sku:
        await state.update_data(new_sku=pending_sku)
        await callback.message.edit_text(
            f"📝 <b>Создание нового товара</b>\n\n"
            f"Артикул (SKU): <code>{pending_sku}</code>\n\n"
            f"Введите название товара:",
            parse_mode="HTML",
        )
        await state.set_state(ReceiveStockFlow.new_product_name)
    else:
        await callback.message.edit_text(
            "📝 <b>Создание нового товара</b>\n\n"
            "Введите артикул (SKU) нового товара:",
            parse_mode="HTML",
        )
        await state.set_state(ReceiveStockFlow.new_product_sku)
    await callback.answer()


@router.message(ReceiveStockFlow.new_product_sku, F.text)
async def receive_new_product_sku(
    message: Message, state: FSMContext, session: AsyncSession
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
            product_name=existing.name,
            product_sku=existing.sku,
        )
        await message.answer(
            f"✅ Товар уже существует: <b>{existing.sku}</b> — {existing.name}\n\n"
            f"Введите количество (сколько пришло):",
            parse_mode="HTML",
        )
        await state.set_state(ReceiveStockFlow.enter_quantity)
        return

    await state.update_data(new_sku=sku)
    await message.answer(
        f"Артикул: <code>{sku}</code>\n\n"
        f"Введите название товара:",
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.new_product_name)


@router.message(ReceiveStockFlow.new_product_name, F.text)
async def receive_new_product_name(
    message: Message, state: FSMContext
) -> None:
    if message.text.strip() in WH_MENU_TEXTS:
        await state.clear()
        return

    name = message.text.strip()
    await state.update_data(new_name=name)
    await message.answer(
        f"Название: <b>{name}</b>\n\n"
        f"Введите цену за единицу (сом):",
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.new_product_price)


@router.message(ReceiveStockFlow.new_product_price, F.text)
async def receive_new_product_price(
    message: Message, state: FSMContext, session: AsyncSession
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
        await message.answer("❌ Введите положительное число (цена в сомах).")
        return

    data = await state.get_data()
    sku = data["new_sku"]
    name = data["new_name"]

    # Create the product
    product = Product(sku=sku, name=name, price=price, is_active=True)
    session.add(product)
    await session.commit()  # Must commit so product exists for the next step

    await state.update_data(
        product_id=product.id,
        product_name=product.name,
        product_sku=product.sku,
    )
    await message.answer(
        f"✅ Товар создан!\n\n"
        f"📦 <b>{sku}</b> — {name}\n"
        f"💰 Цена: {price} сом\n\n"
        f"Введите количество (сколько пришло):",
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.enter_quantity)


# ─── Pagination & selection ──────────────────────────────────────────

@router.callback_query(
    ReceiveStockFlow.select_product, F.data.startswith("receive:page:")
)
async def receive_page_nav(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    page = int(callback.data.split(":")[-1])
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()

    from app.bot.keyboards.inline import catalog_kb

    await callback.message.edit_reply_markup(
        reply_markup=catalog_kb(products, page=page, callback_prefix="receive:page"),
    )
    await callback.answer()


@router.callback_query(
    ReceiveStockFlow.select_product, F.data.startswith("order:select:")
)
async def receive_select_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    product_id = int(callback.data.split(":")[-1])
    product = await session.get(Product, product_id)
    await state.update_data(product_id=product_id, product_name=product.name, product_sku=product.sku)
    await callback.message.edit_text(
        f"📦 <b>{product.sku}</b> — {product.name}\n\n"
        f"Введите количество (сколько пришло):",
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.enter_quantity)
    await callback.answer()


# ─── Enter quantity ──────────────────────────────────────────────────

@router.message(ReceiveStockFlow.enter_quantity)
async def receive_enter_quantity(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    if not message.text or not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("❌ Введите положительное целое число.")
        return

    quantity = int(message.text.strip())
    data = await state.get_data()
    product_id = data["product_id"]
    product_name = data["product_name"]
    product_sku = data["product_sku"]

    # Add to warehouse inventory
    inv_result = await session.execute(
        select(Inventory).where(
            Inventory.store_id == user.store_id,
            Inventory.product_id == product_id,
        )
    )
    inv = inv_result.scalar_one_or_none()
    if inv:
        inv.quantity += quantity
    else:
        inv = Inventory(store_id=user.store_id, product_id=product_id, quantity=quantity)
        session.add(inv)

    await session.commit()

    await message.answer(
        f"✅ Приход оформлен!\n\n"
        f"📦 {product_name} (<code>{product_sku}</code>)\n"
        f"➕ Принято: {quantity} шт\n"
        f"📊 Итого на складе: {inv.quantity} шт",
        parse_mode="HTML",
    )
    await state.clear()
