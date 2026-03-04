from datetime import date, datetime, time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import RoleFilter
from app.bot.keyboards.inline import (
    catalog_kb,
    delivery_accepted_kb,
    delivery_confirm_kb,
    order_action_kb,
    product_select_kb,
)
from app.bot.states.states import OrderFlow, SaleFlow
from app.models.enums import TransactionType, UserRole
from app.models.order import Order
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User
from app.services import notification_service, order_service, transaction_service

router = Router(name="seller")
router.message.filter(RoleFilter(UserRole.SELLER))
router.callback_query.filter(RoleFilter(UserRole.SELLER))



@router.message(F.text == "🛒 Заказ")
async def start_order(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    products = await order_service.get_available_products(session)
    if not products:
        await message.answer("Каталог пуст.")
        return
    await message.answer(
        "🔎 <b>Поиск товара</b>\n\n"
        "Напишите артикул (SKU) или название товара в чат.\n"
        "Либо выберите из каталога ниже:",
        parse_mode="HTML",
        reply_markup=catalog_kb(products, page=0, callback_prefix="order:page")
    )
    await state.set_state(OrderFlow.select_product)


@router.message(OrderFlow.select_product, F.text)
async def search_product(
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
        
        if not products:
            await message.answer("❌ Товар не найден. Попробуйте другой запрос или выберите из списка.")
            return
            
        if len(products) == 1:
            product = products[0]
        else:
            await message.answer(
                "Найдено несколько товаров. Выберите нужный:",
                reply_markup=catalog_kb(products, page=0, callback_prefix="order:page")
            )
            return

    # Product found
    await state.update_data(product_id=product.id)
    await message.answer(
        f"✅ Найден товар: <b>{product.sku}</b> — {product.name}\n\n"
        f"Введите количество (шт):",
        parse_mode="HTML"
    )
    await state.set_state(OrderFlow.enter_quantity)


@router.callback_query(OrderFlow.select_product, F.data.startswith("order:page:"))
async def order_page_nav(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    page = int(callback.data.split(":")[-1])
    products = await order_service.get_available_products(session)
    
    await callback.message.edit_reply_markup(
        reply_markup=catalog_kb(products, page=page, callback_prefix="order:page")
    )
    await callback.answer()


@router.callback_query(OrderFlow.select_product, F.data.startswith("order:select:"))
async def select_product(
    callback: CallbackQuery, state: FSMContext
) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.update_data(product_id=product_id)
    await callback.message.edit_text("Введите количество (шт):")
    await state.set_state(OrderFlow.enter_quantity)
    await callback.answer()


@router.message(OrderFlow.enter_quantity)
async def enter_order_quantity(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Введите целое положительное число.")
        return

    quantity = int(message.text)
    data = await state.get_data()
    product_id = data["product_id"]

    order = await order_service.create_order(
        session, user.store_id, product_id, quantity
    )
    await session.commit()

    product = await session.get(Product, product_id)
    product_name = product.name if product else f"ID:{product_id}"

    await message.answer(
        f"✅ Заявка #{order.id} создана!\n"
        f"Товар: {product_name}, Кол-во: {quantity} шт.\n"
        f"Ожидайте подтверждения от склада."
    )
    await state.clear()

    # Notify warehouse workers instantly
    from app.bot.bot import bot
    await notification_service.notify_warehouse(
        bot=bot,
        session=session,
        text=(
            f"📋 <b>Новая заявка #{order.id}</b>\n"
            f"Магазин: {user.store.name if user.store else '—'}\n"
            f"Товар: {product_name}\n"
            f"Кол-во: {quantity} шт"
        ),
        reply_markup=order_action_kb(order.id),
    )


# ─── Витрина (Мои остатки) ───────────────────────────────────────────


async def _send_vitrine_page(
    message_or_callback: Message | CallbackQuery, 
    items: list, 
    page: int
) -> None:
    from app.bot.keyboards.inline import get_page_slice, add_pagination_buttons
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    limit = 20
    
    if not items:
        text = "Ваша витрина пуста."
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text)
        else:
            await message_or_callback.message.edit_text(text)
        return

    start, end = get_page_slice(len(items), page, limit)
    page_items = items[start:end]

    lines = [f"🖼 <b>Образцы на витрине (стр {page + 1}):</b>\n"]
    for inv in page_items:
        lines.append(
            f"• {inv.product.sku} — {inv.product.name}: "
            f"<b>{inv.quantity}</b> шт"
        )
        
    builder = InlineKeyboardBuilder()
    add_pagination_buttons(builder, len(items), page, limit, "vitrine:page")
    
    markup = builder.as_markup() if len(builder.as_markup().inline_keyboard) > 0 else None
    
    text = "\n".join(lines)
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message_or_callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)


@router.message(F.text == "🖼 Витрина")
async def my_inventory(
    message: Message, user: User, session: AsyncSession
) -> None:
    items = await order_service.get_store_inventory(session, user.store_id)
    await _send_vitrine_page(message, items, page=0)


@router.callback_query(F.data.startswith("vitrine:page:"))
async def vitrine_page_nav(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    page = int(callback.data.split(":")[-1])
    items = await order_service.get_store_inventory(session, user.store_id)
    await _send_vitrine_page(callback, items, page)
    await callback.answer()


# ─── История продаж ──────────────────────────────────────────────────


@router.message(F.text == "📜 Продажи")
async def sales_history(
    message: Message, user: User, session: AsyncSession
) -> None:
    from sqlalchemy.orm import joinedload
    from zoneinfo import ZoneInfo
    
    tz = ZoneInfo("Asia/Dushanbe")
    now_local = datetime.now(tz)
    # Start of today in local time, then converted to UTC for DB query
    today_start_local = datetime.combine(now_local.date(), time.min).replace(tzinfo=tz)
    
    stmt = (
        select(Transaction)
        .options(joinedload(Transaction.product))
        .where(
            Transaction.store_id == user.store_id,
            Transaction.type == TransactionType.SALE,
            Transaction.created_at >= today_start_local,
        )
        .order_by(Transaction.created_at.desc())
        .limit(10)
    )
    result = await session.execute(stmt)
    sales = result.scalars().all()

    if not sales:
        await message.answer("Сегодня продаж ещё не было. 😔")
        return

    lines = ["📜 <b>Последние продажи (сегодня):</b>\n"]
    for txn in sales:
        # DB returns UTC datetime (because DateTime(timezone=True))
        local_time = txn.created_at.astimezone(tz)
        time_str = local_time.strftime("%H:%M")
        product_name = txn.product.name if txn.product else "Товар"
        lines.append(
            f"🕒 {time_str} | {product_name} x{txn.quantity} "
            f"→ <b>{txn.amount} сом</b>"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── Приемка товара (callback от delivery) ───────────────────────────


@router.callback_query(F.data.startswith("order:accept:"))
async def accept_delivery(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        order = await order_service.deliver_order(session, order_id)
        await session.commit()
        await callback.message.edit_text(
            f"✅ Заявка #{order.id} принята!\n"
            f"{order.quantity} шт зачислены на ваш склад.\n\n"
            f"Что дальше?",
            reply_markup=delivery_accepted_kb(order.id),
        )
    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data.startswith("order:sold:"))
async def sold_order(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])

    order = await session.get(Order, order_id)
    if order is None:
        await callback.message.edit_text("❌ Заявка не найдена.")
        await callback.answer()
        return

    product = await session.get(Product, order.product_id)
    if product is None:
        await callback.message.edit_text("❌ Товар не найден.")
        await callback.answer()
        return

    try:
        txn = await transaction_service.record_sale(
            session,
            store_id=order.store_id,
            user_id=user.id,
            product_id=order.product_id,
            quantity=order.quantity,
            price_per_unit=product.price,
        )
        await session.commit()

        await callback.message.edit_text(
            f"💰 Продажа оформлена!\n\n"
            f"Заявка #{order_id}\n"
            f"Товар: {product.name}\n"
            f"Кол-во: {order.quantity} шт\n"
            f"Сумма: {txn.amount} сом ✅"
        )
    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await callback.answer()


@router.callback_query(F.data.startswith("order:return:"))
async def return_order(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])
    from app.models.order import Order

    order = await session.get(Order, order_id)
    if order is None:
        await callback.message.edit_text("❌ Заявка не найдена.")
        await callback.answer()
        return

    product = await session.get(Product, order.product_id)
    if product is None:
        await callback.message.edit_text("❌ Товар не найден.")
        await callback.answer()
        return

    try:
        txn = await transaction_service.record_return(
            session,
            store_id=order.store_id,
            user_id=user.id,
            product_id=order.product_id,
            quantity=order.quantity,
            price_per_unit=product.price,
            reason="Брак/Возврат",
        )
        await session.commit()

        await callback.message.edit_text(
            f"↩️ Возврат оформлен!\n\n"
            f"Заявка #{order_id}\n"
            f"Товар: {product.name}\n"
            f"Кол-во: {order.quantity} шт\n"
            f"Сумма возврата: {txn.amount} сом"
        )
    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await callback.answer()


# ─── Отчет за день ───────────────────────────────────────────────────


@router.message(F.text == "📊 Отчет")
async def daily_report(
    message: Message, user: User, session: AsyncSession
) -> None:
    today_start = datetime.combine(date.today(), time.min)

    # Sales today
    stmt = (
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        )
        .where(
            Transaction.store_id == user.store_id,
            Transaction.type == TransactionType.SALE,
            Transaction.created_at >= today_start,
        )
    )
    result = await session.execute(stmt)
    count, total = result.one()

    store = user.store
    await message.answer(
        f"📊 <b>Отчет за сегодня</b>\n\n"
        f"Продаж: {count}\n"
        f"Сумма: {total} сом\n"
        f"Текущий долг магазина: {store.current_debt} сом",
        parse_mode="HTML",
    )
