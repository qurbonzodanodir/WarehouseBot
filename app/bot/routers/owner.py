from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.bot.filters import RoleFilter
from app.bot.keyboards.inline import collection_amount_kb, stores_debt_kb
from app.bot.states.states import AddProductFlow, AddStockFlow, CashCollectionFlow
from app.models.enums import TransactionType, UserRole
from app.models.store import Store
from app.models.transaction import Transaction
from app.models.user import User
from app.services import transaction_service

router = Router(name="owner")
router.message.filter(RoleFilter(UserRole.OWNER))




@router.message(F.text == "📈 Дашборд за сегодня")
async def dashboard(message: Message, session: AsyncSession) -> None:
    from datetime import date, datetime, time

    today_start = datetime.combine(date.today(), time.min)

    sales_stmt = (
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        ).where(
            Transaction.type == TransactionType.SALE,
            Transaction.created_at >= today_start,
        )
    )
    sales_result = await session.execute(sales_stmt)
    sales_count, sales_total = sales_result.one()

    coll_stmt = (
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0),
        ).where(
            Transaction.type == TransactionType.CASH_COLLECTION,
            Transaction.created_at >= today_start,
        )
    )
    coll_result = await session.execute(coll_stmt)
    coll_count, coll_total = coll_result.one()

    debt_stmt = select(
        func.coalesce(func.sum(Store.current_debt), 0)
    ).where(Store.is_active.is_(True))
    debt_result = await session.execute(debt_stmt)
    total_debt = debt_result.scalar()

    await message.answer(
        f"📈 <b>Дашборд</b>\n\n"
        f"💰 Продажи сегодня: {sales_count} на {sales_total} сом\n"
        f"💸 Инкассация: {coll_count} на {coll_total} сом\n"
        f"📊 Общий долг сети: {total_debt} сом",
        parse_mode="HTML",
    )




@router.message(F.text == "🏪 Рейтинг магазинов")
async def store_ranking(message: Message, session: AsyncSession) -> None:
    from datetime import date, datetime, time

    today_start = datetime.combine(date.today(), time.min)

    stmt = (
        select(
            Store.name,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .join(Transaction, Transaction.store_id == Store.id, isouter=True)
        .where(
            Store.is_active.is_(True),
            Transaction.type == TransactionType.SALE,
            Transaction.created_at >= today_start,
        )
        .group_by(Store.id, Store.name)
        .order_by(func.sum(Transaction.amount).desc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        await message.answer("Нет данных за сегодня.")
        return

    lines = ["🏪 <b>Рейтинг магазинов (продажи сегодня):</b>\n"]
    for i, (name, total) in enumerate(rows, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        lines.append(f"{medal} {name} — {total} сом")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── Популярные товары ───────────────────────────────────────────────


@router.message(F.text == "📦 Популярные товары")
async def popular_products(message: Message, session: AsyncSession) -> None:
    from app.models.product import Product

    stmt = (
        select(
            Product.name,
            func.coalesce(func.sum(Transaction.quantity), 0).label("sold"),
        )
        .join(Transaction, Transaction.product_id == Product.id)
        .where(Transaction.type == TransactionType.SALE)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(Transaction.quantity).desc())
        .limit(10)
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        await message.answer("Нет данных о продажах.")
        return

    lines = ["📦 <b>Топ-10 товаров (по продажам):</b>\n"]
    for i, (name, sold) in enumerate(rows, 1):
        lines.append(f"{i}. {name} — {sold} шт")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ─── Настройки (управление сотрудниками) ─────────────────────────────


@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message, session: AsyncSession) -> None:
    stmt = (
        select(User)
        .options(joinedload(User.store))
        .where(User.is_active.is_(True))
        .order_by(User.role, User.name)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()

    role_emoji = {
        UserRole.SELLER: "🛒",
        UserRole.WAREHOUSE: "🏭",
        UserRole.ADMIN: "🕴️",
        UserRole.OWNER: "👑",
    }

    lines = ["⚙️ <b>Сотрудники системы:</b>\n"]
    for u in users:
        store_name = u.store.name if u.store else "—"
        lines.append(
            f"{role_emoji.get(u.role, '•')} {u.name} | "
            f"{u.role.value} | {store_name}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")




@router.message(F.text == "💸 Начать сбор кассы")
async def start_collection(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    stores = await transaction_service.get_stores_with_debt(session)
    if not stores:
        await message.answer("Нет магазинов с задолженностью. 🎉")
        return
    await message.answer(
        "Выберите магазин для инкассации:",
        reply_markup=stores_debt_kb(stores),
    )
    await state.set_state(CashCollectionFlow.select_store)


@router.callback_query(
    CashCollectionFlow.select_store, F.data.startswith("collect:store:")
)
async def select_store(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    store_id = int(callback.data.split(":")[-1])
    store = await session.get(Store, store_id)
    await state.update_data(store_id=store_id, debt=float(store.current_debt))
    await callback.message.edit_text(
        f"🏪 <b>{store.name}</b>\nДолг: {store.current_debt} сом",
        parse_mode="HTML",
        reply_markup=collection_amount_kb(store_id, float(store.current_debt)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("collect:full:"))
async def collect_full(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    store_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    amount = Decimal(str(data["debt"]))

    txn = await transaction_service.record_cash_collection(
        session, store_id, user.id, amount
    )
    await session.commit()

    await callback.message.edit_text(
        f"✅ Инкассация завершена!\nСобрано: {txn.amount} сом"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("collect:partial:"))
async def collect_partial_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    store_id = int(callback.data.split(":")[-1])
    await state.update_data(store_id=store_id)
    await callback.message.edit_text("Введите сумму, которую забрали (сом):")
    await state.set_state(CashCollectionFlow.enter_amount)
    await callback.answer()


@router.message(CashCollectionFlow.enter_amount)
async def collect_partial_amount(
    message: Message,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer("Введите корректную положительную сумму.")
        return

    data = await state.get_data()
    store_id = data["store_id"]

    txn = await transaction_service.record_cash_collection(
        session, store_id, user.id, amount
    )
    await session.commit()

    store = await session.get(Store, store_id)
    await message.answer(
        f"✅ Инкассация: {txn.amount} сом\n"
        f"Остаток долга: {store.current_debt} сом"
    )
    await state.clear()


@router.callback_query(F.data.startswith("collect:skip:"))
async def collect_skip(
    callback: CallbackQuery, state: FSMContext
) -> None:
    await callback.message.edit_text("⏭ Пропущено.")
    await state.clear()
    await callback.answer()


@router.message(F.text == "📝 Список должников")
async def debtors_list(
    message: Message, session: AsyncSession
) -> None:
    stores = await transaction_service.get_stores_with_debt(session)
    if not stores:
        await message.answer("Все магазины чисты! 🎉")
        return

    lines = ["📝 <b>Список должников:</b>\n"]
    total = Decimal("0")
    for s in stores:
        lines.append(f"• 🏪 {s.name}: <b>{s.current_debt}</b> сом")
        total += s.current_debt
    lines.append(f"\n💰 Итого: <b>{total}</b> сом")
    await message.answer("\n".join(lines), parse_mode="HTML")




@router.message(F.text == "🆕 Добавить товар")
async def btn_add_product(message: Message, state: FSMContext) -> None:
    await message.answer("Введите <b>артикул (SKU)</b> нового товара:", parse_mode="HTML")
    await state.set_state(AddProductFlow.enter_sku)


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

    from app.models.product import Product

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


@router.message(F.text == "📥 Пополнить склад")
async def btn_add_stock(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

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
                text=f"🏪 {s.name}", callback_data=f"stock:store:{s.id}"
            )
        )
    await message.answer("Выберите магазин:", reply_markup=builder.as_markup())
    await state.set_state(AddStockFlow.select_store)


@router.callback_query(AddStockFlow.select_store, F.data.startswith("stock:store:"))
async def stock_select_store(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    store_id = int(callback.data.split(":")[-1])
    store = await session.get(Store, store_id)
    await state.update_data(store_id=store_id, store_name=store.name)

    from app.models.product import Product
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()

    if not products:
        await callback.message.edit_text("Нет товаров. Сначала добавьте товар.")
        await state.clear()
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for p in products:
        builder.row(
            InlineKeyboardButton(
                text=f"{p.sku} — {p.name} ({p.price} сом)",
                callback_data=f"stock:product:{p.id}",
            )
        )
    await callback.message.edit_text(
        f"🏪 <b>{store.name}</b>\n\nВыберите товар:",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(AddStockFlow.select_product)
    await callback.answer()


@router.callback_query(AddStockFlow.select_product, F.data.startswith("stock:product:"))
async def stock_select_product(
    callback: CallbackQuery, state: FSMContext
) -> None:
    product_id = int(callback.data.split(":")[-1])
    await state.update_data(product_id=product_id)
    await callback.message.edit_text("Введите количество (шт/рулонов):")
    await state.set_state(AddStockFlow.enter_quantity)
    await callback.answer()


@router.message(AddStockFlow.enter_quantity)
async def stock_enter_quantity(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("❌ Введите положительное целое число.")
        return

    quantity = int(message.text.strip())
    data = await state.get_data()
    store_id = data["store_id"]
    store_name = data["store_name"]
    product_id = data["product_id"]

    from app.models.inventory import Inventory
    from app.models.product import Product

    product = await session.get(Product, product_id)

    inv_result = await session.execute(
        select(Inventory).where(
            Inventory.store_id == store_id,
            Inventory.product_id == product_id,
        )
    )
    inv = inv_result.scalar_one_or_none()
    if inv:
        inv.quantity += quantity
    else:
        inv = Inventory(store_id=store_id, product_id=product_id, quantity=quantity)
        session.add(inv)

    await session.commit()

    await message.answer(
        f"✅ Склад пополнен!\n\n"
        f"🏪 {store_name}\n"
        f"📦 {product.name} (<code>{product.sku}</code>)\n"
        f"➕ Добавлено: {quantity} шт\n"
        f"📊 Итого на складе: {inv.quantity} шт",
        parse_mode="HTML",
    )
    await state.clear()


