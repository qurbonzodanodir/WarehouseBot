from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import RoleFilter
from app.bot.keyboards.inline import (
    catalog_kb,
    delivery_confirm_kb,
    product_select_kb,
)
from app.bot.states.states import OrderFlow, SaleFlow
from app.models.enums import UserRole
from app.models.user import User
from app.services import order_service, transaction_service

router = Router(name="seller")
router.message.filter(RoleFilter(UserRole.SELLER))
router.callback_query.filter(RoleFilter(UserRole.SELLER))



@router.message(F.text == "📦 Заказать товар")
async def start_order(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    products = await order_service.get_available_products(session)
    if not products:
        await message.answer("Каталог пуст.")
        return
    await message.answer(
        "Выберите товар из каталога:", reply_markup=catalog_kb(products)
    )
    await state.set_state(OrderFlow.select_product)


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

    await message.answer(
        f"✅ Заявка #{order.id} создана!\n"
        f"Товар ID: {product_id}, Кол-во: {quantity} шт.\n"
        f"Ожидайте подтверждения от склада."
    )
    await state.clear()


# ─── Мои остатки ─────────────────────────────────────────────────────


@router.message(F.text == "💼 Мои остатки")
async def my_inventory(
    message: Message, user: User, session: AsyncSession
) -> None:
    items = await order_service.get_store_inventory(session, user.store_id)
    if not items:
        await message.answer("Ваш склад пуст.")
        return

    lines = ["📦 <b>Ваши остатки:</b>\n"]
    for inv in items:
        lines.append(
            f"• {inv.product.sku} — {inv.product.name}: "
            f"<b>{inv.quantity}</b> шт"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── Оформить продажу ────────────────────────────────────────────────


@router.message(F.text == "💰 Оформить продажу")
async def start_sale(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    items = await order_service.get_store_inventory(session, user.store_id)
    if not items:
        await message.answer("Нет товаров для продажи.")
        return
    await message.answer(
        "Выберите товар для продажи:",
        reply_markup=product_select_kb(items),
    )
    await state.set_state(SaleFlow.select_product)


@router.callback_query(SaleFlow.select_product, F.data.startswith("sell:product:"))
async def select_sale_product(
    callback: CallbackQuery, state: FSMContext
) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.update_data(product_id=product_id)
    await callback.message.edit_text("Введите количество проданных единиц:")
    await state.set_state(SaleFlow.enter_quantity)
    await callback.answer()


@router.message(SaleFlow.enter_quantity)
async def enter_sale_quantity(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Введите целое положительное число.")
        return

    quantity = int(message.text)
    data = await state.get_data()
    product_id = data["product_id"]

    try:
        from app.models.product import Product
        product = await session.get(Product, product_id)
        if product is None:
            await message.answer("Товар не найден.")
            await state.clear()
            return

        txn = await transaction_service.record_sale(
            session,
            store_id=user.store_id,
            user_id=user.id,
            product_id=product_id,
            quantity=quantity,
            price_per_unit=product.price,
        )
        await session.commit()
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}")
        await state.clear()
        return

    await message.answer(
        f"✅ Продажа оформлена!\n"
        f"Товар: {product.name}\n"
        f"Кол-во: {quantity} шт\n"
        f"Сумма: {txn.amount} сом"
    )
    await state.clear()


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
            f"✅ Заявка #{order.id} принята! "
            f"{order.quantity} шт зачислены на ваш склад."
        )
    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")
    await callback.answer()


# ─── Отчет за день ───────────────────────────────────────────────────


@router.message(F.text == "📊 Отчет за день")
async def daily_report(
    message: Message, user: User, session: AsyncSession
) -> None:
    from datetime import date, datetime, time

    from sqlalchemy import func, select

    from app.models.transaction import Transaction
    from app.models.enums import TransactionType

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
