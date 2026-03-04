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


@router.message(F.text == "📥 Приход")
async def btn_receive_stock(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()

    from app.bot.keyboards.inline import catalog_kb
    
    if not products:
        await message.answer("Каталог пуст. Попросите владельца добавить товар.")
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
    query = message.text.strip().lower()
    
    # Search by exact SKU first
    result = await session.execute(
        select(Product).where(
            Product.is_active.is_(True),
            func.lower(Product.sku) == query
        )
    )
    product = result.scalar_one_or_none()
    
    # If not found by exact SKU, search by partial name or SKU
    if not product:
        result = await session.execute(
            select(Product).where(
                Product.is_active.is_(True),
                (func.lower(Product.sku).contains(query)) | 
                (func.lower(Product.name).contains(query))
            ).limit(10)
        )
        products = result.scalars().all()
        
        from app.bot.keyboards.inline import catalog_kb
        
        if not products:
            await message.answer("❌ Товар не найден. Попробуйте другой запрос или выберите из списка.")
            return
            
        if len(products) == 1:
            product = products[0]
        else:
            await message.answer(
                "Найдено несколько товаров. Выберите нужный:",
                reply_markup=catalog_kb(products, page=0, callback_prefix="receive:page")
            )
            return

    # Product found
    await state.update_data(product_id=product.id, product_name=product.name, product_sku=product.sku)
    await message.answer(
        f"📦 <b>{product.sku}</b> — {product.name}\n\n"
        f"Введите количество (сколько пришло):",
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.enter_quantity)


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


@router.message(ReceiveStockFlow.enter_quantity)
async def receive_enter_quantity(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    if not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
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
