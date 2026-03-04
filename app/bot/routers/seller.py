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
from app.bot.states.states import OrderFlow, SaleFlow, ReturnFlow
from app.models.enums import TransactionType, UserRole
from app.models.order import Order
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.user import User, UserRole
from app.services import notification_service, order_service, transaction_service
from app.services.product_service import search_store_inventory

router = Router(name="seller")
router.message.filter(RoleFilter(UserRole.SELLER))
router.callback_query.filter(RoleFilter(UserRole.SELLER))

from app.bot.keyboards.reply import SELLER_MENU, SELLER_MORE_MENU

# Menu button texts that should NOT be treated as search queries
MENU_TEXTS = {
    "🖼 Витрина", "🛒 Заказ", "📜 Продажи", "📊 Отчет",
    "Ещё 🔽", "🔙 Назад", "↩️ Сделать возврат",
}

@router.message(F.text == "Ещё 🔽")
async def show_more_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Дополнительные опции:", reply_markup=SELLER_MORE_MENU)


@router.message(F.text == "🔙 Назад")
async def back_to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню:", reply_markup=SELLER_MENU)
@router.message(F.text == "🛒 Заказ")
async def start_order(
    message: Message, user: User, state: FSMContext, session: AsyncSession
) -> None:
    items = await order_service.get_store_inventory(session, user.store_id, include_empty=True)
    if not items:
        await message.answer("Ваша витрина пуста. Сначала склад должен отправить вам образцы.")
        return
        
    products = [inv.product for inv in items] if items else []
    
    await message.answer(
        "🔎 <b>Поиск товара для заказа</b>\n\n"
        "Напишите артикул (SKU) или название товара из **вашей витрины**.\n"
        "Либо выберите из списка ниже:",
        parse_mode="HTML",
        reply_markup=catalog_kb(products, page=0, callback_prefix="order:page")
    )
    await state.set_state(OrderFlow.select_product)


@router.message(OrderFlow.select_product, F.text)
async def search_product(
    message: Message, user: User, state: FSMContext, session: AsyncSession
) -> None:
    if message.text.strip() in MENU_TEXTS:
        await state.clear()
        return

    product, matches, _inv = await search_store_inventory(
        session, message.text, user.store_id, require_stock=False
    )

    if product:
        # Exact match — skip to quantity
        pass  # handled below
    elif matches:
        from app.bot.keyboards.inline import catalog_kb
        await message.answer(
            "Найдено по вашему запросу. Выберите нужный товар:",
            reply_markup=catalog_kb(matches, page=0, callback_prefix="order:page")
        )
        return
    else:
        await message.answer("❌ Товар не найден на вашей витрине. Проверьте запрос.")
        return

    # Exact product found
    await state.update_data(product_id=product.id)
    await message.answer(
        f"✅ Найден товар с витрины: <b>{product.sku}</b> — {product.name}\n\n"
        f"Введите количество для заказа (шт):",
        parse_mode="HTML"
    )
    await state.set_state(OrderFlow.enter_quantity)


@router.callback_query(OrderFlow.select_product, F.data.startswith("order:page:"))
async def order_page_nav(
    callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession
) -> None:
    page = int(callback.data.split(":")[-1])
    
    from sqlalchemy.orm import selectinload
    result = await session.execute(
        select(Inventory)
        .options(selectinload(Inventory.product))
        .where(
            Inventory.store_id == user.store_id
        )
    )
    items = result.scalars().all()
    products = [inv.product for inv in items] if items else []
    
    from app.bot.keyboards.inline import catalog_kb
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
    message: Message, user: User, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
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
    message: Message, user: User, state: FSMContext, session: AsyncSession
) -> None:
    await state.clear()
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
            order_id=order.id,
        )
        await session.commit()

        # Update the message and remove the buttons so they can't be clicked again
        await callback.message.edit_text(
            f"💰 Продажа оформлена!\n\n"
            f"Ордер/Заявка #{order_id}\n"
            f"Товар: <b>{product.name}</b>\n"
            f"Кол-во: {order.quantity} шт\n"
            f"Сумма: <b>{txn.amount} сом</b> ✅",
            parse_mode="HTML"
        )
    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка выкупа: {e}")
    except Exception as e:
        await callback.message.edit_text("❌ Произошла ошибка. Обратитесь к администратору.")
        print(f"Error in sold_order: {e}")
    finally:
        await callback.answer()


@router.callback_query(F.data.startswith("order:return:"))
async def return_order(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        from app.models.order import Order
        from app.models.enums import OrderStatus
        from sqlalchemy.orm import selectinload

        # 1. Get the original delivered order
        original_order = await session.get(Order, order_id, options=[selectinload(Order.product)])
        if not original_order:
            await callback.answer("Заказ не найден.", show_alert=True)
            return

        product_id = original_order.product_id
        quantity = original_order.quantity

        # 2. Check if the store actually has this quantity available (it should, as they just received it)
        from app.models.inventory import Inventory
        from sqlalchemy import select
        
        inv_stmt = select(Inventory).where(
            Inventory.store_id == user.store_id,
            Inventory.product_id == product_id
        )
        inv_result = await session.execute(inv_stmt)
        inv = inv_result.scalar_one_or_none()
        
        if not inv or inv.quantity < quantity:
            await callback.answer(
                "❌ На витрине недостаточно товара для возврата всей партии. "
                "Используйте ручной возврат через меню «Ещё».", 
                show_alert=True
            )
            return

        # 3. Create a new RETURN_PENDING order
        return_order = Order(
            store_id=user.store_id,
            product_id=product_id,
            quantity=quantity,
            status=OrderStatus.RETURN_PENDING,
        )
        session.add(return_order)
        await session.flush()

        # 4. Initiate the return transaction (locks inventory, waits for warehouse approval)
        await transaction_service.initiate_return(
            session,
            store_id=user.store_id,
            user_id=user.id,
            product_id=product_id,
            quantity=quantity,
            order_id=return_order.id,
        )
        await session.commit()

        # 5. Notify the seller
        await callback.message.edit_text(
            f"✅ <b>Товар отправлен на возврат!</b>\n\n"
            f"Заявка #{return_order.id}\n"
            f"Товар: <b>{original_order.product.name}</b>\n"
            f"Кол-во: {quantity} шт\n\n"
            f"<i>Партия списана с витрины. Ожидайте подтверждения от склада.</i>",
            parse_mode="HTML"
        )
        
        # 6. Notify the warehouse
        from app.bot.bot import bot
        from app.bot.keyboards.inline import warehouse_return_kb
        await notification_service.notify_warehouse(
            bot=bot,
            session=session,
            text=(
                f"🔄 <b>Быстрый возврат от {user.store.name if user.store else 'Магазина'}</b>\n\n"
                f"Заявка #{return_order.id}\n"
                f"Товар: {original_order.product.name} ({original_order.product.sku})\n"
                f"Кол-во: {quantity} шт\n\n"
                f"Примите товар физически и нажмите 'Принять возврат', чтобы списать долг магазина."
            ),
            reply_markup=warehouse_return_kb(return_order.id)
        )

    except ValueError as e:
        await callback.message.edit_text(f"❌ Ошибка возврата: {e}")
    except Exception as e:
        await callback.message.edit_text("❌ Произошла ошибка. Обратитесь к администратору.")
        print(f"Error in quick return_order: {e}")
    finally:
        await callback.answer()


# ─── Самостоятельный возврат с витрины (ReturnFlow) ───────────────────────────

@router.message(F.text == "↩️ Сделать возврат")
async def start_return(
    message: Message, user: User, state: FSMContext, session: AsyncSession
) -> None:
    items = await order_service.get_store_inventory(session, user.store_id, include_empty=False)
    if not items:
        await message.answer("У вас нет товаров в наличии для возврата.")
        return
        
    products = [inv.product for inv in items if inv.quantity > 0]
    if not products:
        await message.answer("На вашей витрине нет доступных товаров для возврата (количество равно 0).")
        return
    
    await message.answer(
        "🔄 <b>Оформление возврата на Склад</b>\n\n"
        "Напишите артикул (SKU) или название товара из **вашей витрины**.\n"
        "Либо выберите из списка ниже:",
        parse_mode="HTML",
        reply_markup=catalog_kb(
            products, 
            page=0, 
            callback_prefix="return:page", 
            item_callback_prefix="return:select"
        )
    )
    await state.set_state(ReturnFlow.select_product)


@router.message(ReturnFlow.select_product, F.text)
async def return_search_product(
    message: Message, user: User, state: FSMContext, session: AsyncSession
) -> None:
    if message.text.strip() in MENU_TEXTS:
        await state.clear()
        return

    product, matches, inv = await search_store_inventory(
        session, message.text, user.store_id, require_stock=True
    )

    if product:
        # Exact match — skip to quantity
        pass  # handled below
    elif matches:
        from app.bot.keyboards.inline import catalog_kb
        await message.answer(
            "Найдено по вашему запросу. Выберите товар для возврата:",
            reply_markup=catalog_kb(
                matches,
                page=0,
                callback_prefix="return:page",
                item_callback_prefix="return:select"
            )
        )
        return
    else:
        await message.answer("❌ Товар не найден на вашей витрине, либо его количество равно 0.")
        return

    # Exact product found
    await state.update_data(product_id=product.id)
    await message.answer(
        f"✅ Найден товар: <b>{product.sku}</b> — {product.name} (В наличии: {inv.quantity} шт)\n\n"
        f"Введите количество для возврата (шт):",
        parse_mode="HTML"
    )
    await state.set_state(ReturnFlow.enter_quantity)


@router.callback_query(ReturnFlow.select_product, F.data.startswith("return:page:"))
async def return_page_nav(
    callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession
) -> None:
    page = int(callback.data.split(":")[-1])
    
    from sqlalchemy.orm import selectinload
    from app.models.inventory import Inventory
    result = await session.execute(
        select(Inventory)
        .options(selectinload(Inventory.product))
        .where(
            Inventory.store_id == user.store_id,
            Inventory.quantity > 0
        )
    )
    items = result.scalars().all()
    products = [inv.product for inv in items] if items else []
    
    from app.bot.keyboards.inline import catalog_kb
    await callback.message.edit_reply_markup(
        reply_markup=catalog_kb(
            products, 
            page=page, 
            callback_prefix="return:page",
            item_callback_prefix="return:select"
        )
    )
    await callback.answer()


@router.callback_query(ReturnFlow.select_product, F.data.startswith("return:select:"))
async def return_select_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    product_id = int(callback.data.split(":")[-1])
    
    from app.models.inventory import Inventory
    result = await session.execute(
        select(Inventory).where(Inventory.store_id == user.store_id, Inventory.product_id == product_id)
    )
    inv = result.scalar_one_or_none()
    qty = inv.quantity if inv else 0
    
    await state.update_data(product_id=product_id)
    await callback.message.edit_text(f"Введите количество для возврата (доступно {qty} шт):")
    await state.set_state(ReturnFlow.enter_quantity)
    await callback.answer()


@router.message(ReturnFlow.enter_quantity)
async def return_enter_quantity(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Введите целое положительное число.")
        return

    quantity = int(message.text)
    data = await state.get_data()
    product_id = data["product_id"]

    product = await session.get(Product, product_id)
    if product is None:
        await message.answer("❌ Товар не найден.")
        await state.clear()
        return

    from app.models.order import Order
    from app.models.enums import OrderStatus
    
    # 1. Create a "return" order
    order = Order(
        store_id=user.store_id,
        product_id=product_id,
        quantity=quantity,
        status=OrderStatus.RETURN_PENDING,
    )
    session.add(order)
    await session.flush()

    try:
        # 2. Initiate return (locks inventory without changing debt)
        await transaction_service.initiate_return(
            session,
            store_id=user.store_id,
            user_id=user.id,
            product_id=product_id,
            quantity=quantity,
            order_id=order.id,
        )
        await session.commit()

        await message.answer(
            f"📦 Возврат инициирован!\n\n"
            f"Заявка #{order.id}\n"
            f"Товар: <b>{product.name}</b>\n"
            f"Кол-во: {quantity} шт\n\n"
            f"<i>Товар ({quantity} шт) списан с вашей витрины. Ожидается физическая передача рулонов на Главный Склад для подтверждения списания вашего долга.</i>",
            parse_mode="HTML"
        )
        
        # Notify warehouse
        from app.bot.bot import bot
        from app.bot.keyboards.inline import warehouse_return_kb
        await notification_service.notify_warehouse(
            bot=bot,
            session=session,
            text=(
                f"🔄 <b>Возврат от {user.store.name if user.store else 'Магазина'}</b>\n\n"
                f"Заявка #{order.id}\n"
                f"Товар: {product.name} ({product.sku})\n"
                f"Кол-во: {quantity} шт\n\n"
                f"Примите товар физически и нажмите 'Принять возврат', чтобы списать долг магазина."
            ),
            reply_markup=warehouse_return_kb(order.id)
        )
        
    except ValueError as e:
        await message.answer(f"❌ Ошибка возврата: {e}")
    except Exception as e:
        await message.answer("❌ Произошла ошибка. Обратитесь к администратору.")
        print(f"Error in return_enter_quantity: {e}")
    finally:
        await state.clear()


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


# ─── Display Transfer Callbacks ──────────────────────────────────────

@router.callback_query(F.data.startswith("display:receive:"))
async def seller_receive_display(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])
    from app.models.order import Order
    from app.models.enums import OrderStatus
    from sqlalchemy.orm import selectinload

    order = await session.get(
        Order, order_id, options=[selectinload(Order.product)]
    )
    if not order or order.status != OrderStatus.DISPLAY_DISPATCHED:
        await callback.answer("❌ Заявка не найдена или уже обработана.", show_alert=True)
        return

    # Credit store inventory
    from app.models.inventory import Inventory
    stmt = select(Inventory).where(
        Inventory.store_id == order.store_id,
        Inventory.product_id == order.product_id,
    )
    result = await session.execute(stmt)
    inv = result.scalar_one_or_none()
    if inv:
        inv.quantity += order.quantity
    else:
        inv = Inventory(
            store_id=order.store_id, product_id=order.product_id, quantity=order.quantity
        )
        session.add(inv)

    order.status = OrderStatus.DISPLAY_DELIVERED
    await session.commit()

    await callback.message.edit_text(
        f"✅ <b>Образцы приняты на витрину!</b>\n\n"
        f"📦 {order.product.sku} — {order.product.name}\n"
        f"🔢 Количество: {order.quantity} шт\n"
        f"📍 Теперь товар доступен в вашей витрине.",
        parse_mode="HTML",
    )
    await callback.answer("Товар зачислен на витрину")


@router.callback_query(F.data.startswith("display:reject:"))
async def seller_reject_display(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    order_id = int(callback.data.split(":")[-1])
    from app.models.order import Order
    from app.models.enums import OrderStatus
    from sqlalchemy.orm import selectinload

    order = await session.get(
        Order, order_id, options=[selectinload(Order.product)]
    )
    if not order or order.status != OrderStatus.DISPLAY_DISPATCHED:
        await callback.answer("❌ Заявка не найдена или уже обработана.", show_alert=True)
        return

    # 1. Return quantity to warehouse
    # Find warehouse store (any user with WAREHOUSE role)
    wh_user_stmt = select(User).where(User.role == UserRole.WAREHOUSE).limit(1)
    wh_user_res = await session.execute(wh_user_stmt)
    wh_user = wh_user_res.scalar_one_or_none()
    
    if wh_user:
        from app.models.inventory import Inventory
        wh_inv_stmt = select(Inventory).where(
            Inventory.store_id == wh_user.store_id,
            Inventory.product_id == order.product_id,
        )
        wh_inv_res = await session.execute(wh_inv_stmt)
        wh_inv = wh_inv_res.scalar_one_or_none()
        if wh_inv:
            wh_inv.quantity += order.quantity
        else:
            # Should not happen as it was just deducted, but to be safe:
            wh_inv = Inventory(
                store_id=wh_user.store_id, product_id=order.product_id, quantity=order.quantity
            )
            session.add(wh_inv)

    order.status = OrderStatus.DISPLAY_REJECTED
    await session.commit()

    # 2. Notify seller
    await callback.message.edit_text(
        f"❌ <b>Вы отметили, что не получили товар.</b>\n\n"
        f"📦 {order.product.sku} — {order.product.name}\n"
        f"🔢 Количество: {order.quantity} шт\n\n"
        f"⚠️ Уведомление отправлено на склад. Товар возвращен в остатки склада.",
        parse_mode="HTML",
    )

    # 3. Notify warehouse
    from app.bot.bot import bot
    await notification_service.notify_warehouse(
        bot=bot,
        session=session,
        text=(
            f"🚫 <b>ОТМЕНА ПРИЁМКИ ОБРАЗЦОВ</b>\n\n"
            f"Магазин: <b>{user.store.name if user.store else 'Неизвестно'}</b>\n"
            f"Заявка: #{order.id}\n"
            f"Товар: {order.product.sku} — {order.product.name}\n"
            f"Количество: {order.quantity} шт\n\n"
            f"❌ Продавец нажал <b>'Не получил'</b>. Товар автоматически возвращен в ваш остаток."
        )
    )
    await callback.answer("Уведомление отправлено на склад", show_alert=True)

