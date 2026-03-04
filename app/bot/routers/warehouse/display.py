from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.states.states import DisplayTransferFlow
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.store import Store
from app.models.user import User

router = Router(name="warehouse.display")


@router.message(F.text == "📋 Образцы")
async def btn_display_transfer(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    result = await session.execute(
        select(Store).where(Store.is_active.is_(True)).order_by(Store.id)
    )
    stores = result.scalars().all()

    if not stores:
        await message.answer("Нет магазинов.")
        return

    builder = InlineKeyboardBuilder()
    for s in stores:
        builder.row(
            InlineKeyboardButton(
                text=f"🏪 {s.name}", callback_data=f"display:store:{s.id}"
            )
        )
    await message.answer(
        "📋 <b>Отправить образцы</b>\n\nВыберите магазин:",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(DisplayTransferFlow.select_store)


@router.callback_query(
    DisplayTransferFlow.select_store, F.data.startswith("display:store:")
)
async def display_select_store(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession
) -> None:
    store_id = int(callback.data.split(":")[-1])
    store = await session.get(Store, store_id)
    await state.update_data(target_store_id=store_id, target_store_name=store.name)

    # Show warehouse inventory
    result = await session.execute(
        select(Inventory)
        .join(Product)
        .where(
            Inventory.store_id == user.store_id,
            Inventory.quantity > 0,
            Product.is_active.is_(True),
        )
        .order_by(Product.sku)
    )
    items = result.scalars().all()

    if not items:
        await callback.message.edit_text("Склад пуст — нечего отправлять.")
        await state.clear()
        await callback.answer()
        return

    from app.bot.keyboards.inline import product_select_kb

    await callback.message.edit_text(
        f"🏪 <b>{store.name}</b>\n\nВыберите товар для витрины:",
        parse_mode="HTML",
        reply_markup=product_select_kb(
            items, page=0, callback_prefix="display:page", item_callback_prefix="display:product"
        ),
    )
    await state.set_state(DisplayTransferFlow.select_product)
    await callback.answer()

@router.callback_query(
    DisplayTransferFlow.select_product, F.data.startswith("display:page:")
)
async def display_page_nav(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession
) -> None:
    page = int(callback.data.split(":")[-1])
    
    result = await session.execute(
        select(Inventory)
        .join(Product)
        .where(
            Inventory.store_id == user.store_id,
            Inventory.quantity > 0,
            Product.is_active.is_(True),
        )
        .order_by(Product.sku)
    )
    items = result.scalars().all()
    
    data = await state.get_data()
    store_name = data.get("target_store_name", "Магазин")
    
    from app.bot.keyboards.inline import product_select_kb
    
    await callback.message.edit_reply_markup(
        reply_markup=product_select_kb(
            items, page=page, callback_prefix="display:page", item_callback_prefix="display:product"
        ),
    )
    await callback.answer()


@router.callback_query(
    DisplayTransferFlow.select_product, F.data.startswith("display:product:")
)
async def display_select_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    product_id = int(callback.data.split(":")[-1])
    product = await session.get(Product, product_id)
    await state.update_data(product_id=product_id, product_name=product.name, product_sku=product.sku)
    await callback.message.edit_text(
        f"📦 <b>{product.sku}</b> — {product.name}\n\n"
        f"Сколько рулонов отправить для витрины? (обычно 1–2):",
        parse_mode="HTML",
    )
    await state.set_state(DisplayTransferFlow.enter_quantity)
    await callback.answer()


@router.message(DisplayTransferFlow.enter_quantity)
async def display_enter_quantity(
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
    target_store_id = data["target_store_id"]
    target_store_name = data["target_store_name"]

    # Check warehouse stock
    wh_result = await session.execute(
        select(Inventory).where(
            Inventory.store_id == user.store_id,
            Inventory.product_id == product_id,
        )
    )
    wh_inv = wh_result.scalar_one_or_none()
    if wh_inv is None or wh_inv.quantity < quantity:
        available = wh_inv.quantity if wh_inv else 0
        await message.answer(
            f"❌ Недостаточно на складе: есть {available}, нужно {quantity}."
        )
        return

    # Deduct from warehouse
    wh_inv.quantity -= quantity

    # Add to store
    store_result = await session.execute(
        select(Inventory).where(
            Inventory.store_id == target_store_id,
            Inventory.product_id == product_id,
        )
    )
    store_inv = store_result.scalar_one_or_none()
    if store_inv:
        store_inv.quantity += quantity
    else:
        store_inv = Inventory(
            store_id=target_store_id, product_id=product_id, quantity=quantity
        )
        session.add(store_inv)

    # NOTE: no debt increase — this is a display transfer, not a sale!
    await session.commit()

    await message.answer(
        f"✅ Образцы отправлены!\n\n"
        f"🏪 {target_store_name}\n"
        f"📦 {product_name} (<code>{product_sku}</code>)\n"
        f"📋 Отправлено: {quantity} шт (витрина)\n"
        f"📊 Остаток на складе: {wh_inv.quantity} шт\n\n"
        f"💡 Долг магазина <b>не увеличен</b> — это образцы.",
        parse_mode="HTML",
    )
    await state.clear()
