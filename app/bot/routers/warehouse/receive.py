from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
from app.bot.states.states import ReceiveStockFlow
from app.models.product import Product
from app.models.user import User

router = Router(name="warehouse.receive")

# Menu texts that should NOT be treated as search queries
WH_MENU_TEXTS = {
    "📥 Приход", "📋 Образцы", "🔔 Запросы", "📦 Остатки",
    "🚚 Отгрузки", "Ещё 🔽", "🔙 Назад",
    "📥 Қабули мол", "📋 Намунаҳо", "🔔 Дархостҳо", "📦 Боқимонда",
    "🚚 Ирсолҳо", "Боз 🔽", "🔙 Ба қафо",
}


@router.message(F.text.in_({"📥 Приход", "📥 Қабули мол"}))
async def btn_receive_stock(
    message: Message, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    await state.clear()
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()

    from app.bot.keyboards.inline import catalog_kb

    if not products:
        await message.answer(
            _("catalog_empty"),
            parse_mode="HTML",
        )
        return

    await message.answer(
        _("receive_title"),
        parse_mode="HTML",
        reply_markup=catalog_kb(
            products, 
            page=0, 
            callback_prefix="receive:page", 
            item_callback_prefix="receive:select",
            _=_
        ),
    )
    await state.set_state(ReceiveStockFlow.select_product)


@router.message(ReceiveStockFlow.select_product, F.text)
async def receive_search_product(
    message: Message, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    if message.text.strip() in WH_MENU_TEXTS:
        await state.clear()
        return

    from app.services import ProductService
    prod_svc = ProductService(session)
    product, matches = await prod_svc.search_catalog(message.text)

    if product:
        # Exact match
        await state.update_data(product_id=product.id, product_sku=product.sku)
        await message.answer(
            _("receive_selected", sku=product.sku),
            parse_mode="HTML",
        )
        await state.set_state(ReceiveStockFlow.enter_quantity)
        return

    if matches:
        from app.bot.keyboards.inline import catalog_kb
        await message.answer(
            _("return_search_found"),
            reply_markup=catalog_kb(
                matches, 
                page=0, 
                callback_prefix="receive:page", 
                item_callback_prefix="receive:select",
                _=_
            )
        )
        return

    await message.answer(
        _("receive_not_found", text=message.text.strip()),
        parse_mode="HTML",
    )


# ─── Create new product inline ───────────────────────────────────────




# ─── Pagination & selection ──────────────────────────────────────────

@router.callback_query(
    ReceiveStockFlow.select_product, F.data.startswith("receive:page:")
)
async def receive_page_nav(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    page = int(callback.data.split(":")[-1])
    result = await session.execute(
        select(Product).where(Product.is_active.is_(True)).order_by(Product.sku)
    )
    products = result.scalars().all()

    from app.bot.keyboards.inline import catalog_kb

    await callback.message.edit_reply_markup(
        reply_markup=catalog_kb(
            products, 
            page=page, 
            callback_prefix="receive:page", 
            item_callback_prefix="receive:select",
            _=_
        ),
    )
    await callback.answer()


@router.callback_query(
    ReceiveStockFlow.select_product, F.data.startswith("receive:select:")
)
async def receive_select_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    product_id = int(callback.data.split(":")[-1])
    product = await session.get(Product, product_id)
    await state.update_data(product_id=product_id, product_sku=product.sku)
    await callback.message.edit_text(
        _("receive_selected", sku=product.sku),
        parse_mode="HTML",
    )
    await state.set_state(ReceiveStockFlow.enter_quantity)
    await callback.answer()


# ─── Enter quantity ──────────────────────────────────────────────────

@router.message(ReceiveStockFlow.enter_quantity)
async def receive_enter_quantity(
    message: Message, state: FSMContext, user: User, session: AsyncSession, _: Any
) -> None:
    if not message.text or not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer(_("sale_invalid_qty"))
        return

    quantity = int(message.text.strip())
    data = await state.get_data()
    product_id = data["product_id"]
    product_sku = data["product_sku"]

    from app.services import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        await message.answer(_("warehouse_not_found"))
        return

    from app.services import TransactionService
    txn_svc = TransactionService(session)

    inv = await txn_svc.receive_stock(
        warehouse_store_id=warehouse_id,
        product_id=product_id,
        quantity=quantity,
        user_id=user.id,
    )
    await session.commit()

    await message.answer(
        _("receive_success", sku=product_sku, qty=quantity, total=inv.quantity),
        parse_mode="HTML",
    )
    await state.clear()
