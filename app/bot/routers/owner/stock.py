from aiogram import F, Router
from typing import Any
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import catalog_kb
from app.bot.states.states import AddStockFlow
from app.models.product import Product
from app.models.store import Store
from app.models.enums import StockMovementType
from app.services import TransactionService
from app.core.config import settings

router = Router(name="owner.stock")


@router.message(F.text.in_({"📥 Пополнить склад", "📥 Пур кардани анбор"}))
async def stock_replenish_start(
    message: Message, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    """Start the replenishment flow for the main warehouse."""
    await state.clear()
    
    # Get all active products from catalog
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()
    
    if not products:
        await message.answer(_("stock_invalid_catalog"))
        return
        
    await message.answer(
        _("stock_replenish_title"),
        parse_mode="HTML",
        reply_markup=catalog_kb(
            products, 
            page=0, 
            callback_prefix="stock:page", 
            item_callback_prefix="stock:select",
            _=_
        )
    )
    await state.set_state(AddStockFlow.select_product)


@router.callback_query(AddStockFlow.select_product, F.data.startswith("stock:page:"))
async def stock_page_nav(callback: CallbackQuery, session: AsyncSession, _: Any) -> None:
    page = int(callback.data.split(":")[-1])
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()
    
    await callback.message.edit_reply_markup(
        reply_markup=catalog_kb(
            products, 
            page=page, 
            callback_prefix="stock:page", 
            item_callback_prefix="stock:select",
            _=_
        )
    )
    await callback.answer()


@router.callback_query(AddStockFlow.select_product, F.data.startswith("stock:select:"))
async def stock_select_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    product_id = int(callback.data.split(":")[-1])
    product = await session.get(Product, product_id)
    
    await state.update_data(product_id=product_id)
    await callback.message.edit_text(
        _("stock_enter_qty", sku=product.sku),
        parse_mode="HTML"
    )
    await state.set_state(AddStockFlow.enter_quantity)
    await callback.answer()


@router.message(AddStockFlow.enter_quantity)
async def stock_enter_quantity(
    message: Message, state: FSMContext, session: AsyncSession, user: "User", _: Any # user from middleware
) -> None:
    try:
        qty = int(message.text.strip())
        if qty <= 0:
            raise ValueError
    except ValueError:
        await message.answer(_("stock_invalid_qty"))
        return

    quantity = int(message.text)
    data = await state.get_data()
    product_id = data.get("product_id")
    
    try:
        from app.models.inventory import Inventory
        from app.models.product import Product
        
        product = await session.get(Product, product_id)
        
        # Use TransactionService to ensure proper inventory locking and recording
        txn_svc = TransactionService(session)
        
        from app.services import StoreService
        store_svc = StoreService(session)
        warehouse_id = await store_svc.get_main_warehouse_id()
        if warehouse_id is None:
            await message.answer(_("stock_wh_not_found"))
            return

        # 1. Update Inventory WITH LOCK
        inv = await txn_svc._get_or_create_inventory(warehouse_id, product_id, lock=True)
        inv.quantity += quantity
        
        # 2. Record movement
        await txn_svc.record_stock_movement(
            product_id=product_id,
            quantity=quantity,
            movement_type=StockMovementType.RECEIVE_FROM_SUPPLIER,
            to_store_id=warehouse_id,
            user_id=user.id
        )
        
        await session.commit()
        
        await message.answer(
            _("stock_success", sku=product.sku, qty=qty),
            parse_mode="HTML",
        )
        await state.clear()
        
    except Exception as e:
        await message.answer(_("stock_replenish_error"))
        print(f"Stock replenishment error: {e}")
        await session.rollback()
