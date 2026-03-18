from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload
from app.bot.states.states import DisplayTransferFlow
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.store import Store
from app.models.user import User
from typing import Any

router = Router(name="warehouse.display")


@router.message(F.text.in_({"📋 Образцы", "📋 Намунаҳо"}))
async def btn_display_transfer(
    message: Message, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    from app.services import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()

    result = await session.execute(
        select(Store)
        .where(Store.is_active.is_(True), Store.id != warehouse_id)
        .order_by(Store.id)
    )
    stores = result.scalars().all()

    if not stores:
        await message.answer(_("stores_not_found"))
        return

    builder = InlineKeyboardBuilder()
    for s in stores:
        builder.row(
            InlineKeyboardButton(
                text=f"🏪 {s.name}", callback_data=f"display:store:{s.id}"
            )
        )
    await message.answer(
        _("display_transfer_title"),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(DisplayTransferFlow.select_store)


@router.callback_query(
    DisplayTransferFlow.select_store, F.data.startswith("display:store:")
)
async def display_select_store(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, _: Any
) -> None:
    store_id = int(callback.data.split(":")[-1])
    store = await session.get(Store, store_id)
    await state.update_data(target_store_id=store_id, target_store_name=store.name)

    from app.services import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        await callback.message.edit_text(_("warehouse_not_found"))
        await state.clear()
        return

    # Show warehouse inventory
    result = await session.execute(
        select(Inventory)
        .options(selectinload(Inventory.product))
        .join(Product)
        .where(
            Inventory.store_id == warehouse_id,
            Inventory.quantity > 0,
            Product.is_active.is_(True),
        )
        .order_by(Product.sku)
    )
    items = result.scalars().all()

    if not items:
        await callback.message.edit_text(_("stock_empty"))
        await state.clear()
        await callback.answer()
        return

    from app.bot.keyboards.inline import product_select_kb

    await callback.message.edit_text(
        _("display_select_product_title", store=store.name),
        parse_mode="HTML",
        reply_markup=product_select_kb(
            items, page=0, callback_prefix="display:page", item_callback_prefix="display:product", _=_
        ),
    )
    await state.set_state(DisplayTransferFlow.select_product)
    await callback.answer()

@router.callback_query(
    DisplayTransferFlow.select_product, F.data.startswith("display:page:")
)
async def display_page_nav(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, _: Any
) -> None:
    page = int(callback.data.split(":")[-1])
    
    from app.services import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        return

    result = await session.execute(
        select(Inventory)
        .options(selectinload(Inventory.product))
        .join(Product)
        .where(
            Inventory.store_id == warehouse_id,
            Inventory.quantity > 0,
            Product.is_active.is_(True),
        )
        .order_by(Product.sku)
    )
    items = result.scalars().all()
    
    data = await state.get_data()
    store_name = data.get("target_store_name", _("store_label"))
    
    from app.bot.keyboards.inline import product_select_kb
    
    await callback.message.edit_reply_markup(
        reply_markup=product_select_kb(
            items, page=page, callback_prefix="display:page", item_callback_prefix="display:product", _=_
        ),
    )
    await callback.answer()


@router.callback_query(
    DisplayTransferFlow.select_product, F.data.startswith("display:product:")
)
async def display_select_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    product_id = int(callback.data.split(":")[-1])
    product = await session.get(Product, product_id)
    await state.update_data(product_id=product_id, product_sku=product.sku)
    await callback.message.edit_text(
        _("display_enter_qty_title", sku=product.sku),
        parse_mode="HTML",
    )
    await state.set_state(DisplayTransferFlow.enter_quantity)
    await callback.answer()


@router.message(DisplayTransferFlow.enter_quantity)
async def display_enter_quantity(
    message: Message, state: FSMContext, user: User, session: AsyncSession, _: Any
) -> None:
    if not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer(_("sale_invalid_qty"))
        return

    quantity = int(message.text.strip())
    data = await state.get_data()
    product_id = data["product_id"]
    product_sku = data["product_sku"]
    target_store_id = data["target_store_id"]
    target_store_name = data["target_store_name"]

    from app.services import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        await message.answer(_("warehouse_not_found"))
        return

    # Check warehouse stock
    wh_result = await session.execute(
        select(Inventory).where(
            Inventory.store_id == warehouse_id,
            Inventory.product_id == product_id,
        )
    )
    wh_inv = wh_result.scalar_one_or_none()
    if wh_inv is None or wh_inv.quantity < quantity:
        available = wh_inv.quantity if wh_inv else 0
        await message.answer(
            _("display_not_enough_stock", available=available, qty=quantity)
        )
        return

    # 1. Deduct from warehouse immediately (reserve)
    wh_inv.quantity -= quantity

    # 2. Create a special "Order" for tracking display transfer
    from app.models.order import Order
    from app.models.enums import OrderStatus
    
    display_order = Order(
        store_id=target_store_id,
        product_id=product_id,
        quantity=quantity,
        status=OrderStatus.DISPLAY_DISPATCHED
    )
    session.add(display_order)
    await session.flush()  # Get display_order.id
    
    from app.services import TransactionService
    from app.models.enums import StockMovementType
    txn_svc = TransactionService(session)
    await txn_svc.record_stock_movement(
        product_id=product_id, quantity=quantity,
        movement_type=StockMovementType.DISPLAY_DISPATCH,
        from_store_id=warehouse_id, to_store_id=target_store_id, user_id=user.id
    )

    await session.commit()

    # 3. Notify the seller of the target store
    from app.services import NotificationService
    from app.bot.keyboards.inline import display_receive_kb

    
    # Notify target store sellers
    notif_svc = NotificationService(message.bot, session)
    await notif_svc.notify_sellers(
        store_id=target_store_id,
        text=lambda _t: _t("display_dispatched_seller_notif", sku=product_sku, qty=quantity),
        reply_markup=lambda _t: display_receive_kb(display_order.id, _=_t),
    )

    await message.answer(
        _("display_dispatch_success_wh", store=target_store_name, sku=product_sku, qty=quantity, total=wh_inv.quantity),
        parse_mode="HTML",
    )
    await state.clear()
