
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bot.states.states import SaleFlow
from app.bot.routers.seller.catalog_ui import clean_search_query, product_card, product_matches, send_catalog_page
from app.models.user import User
from app.services import OrderService, TransactionService
from app.bot.routers.seller.common import MENU_TEXTS
from typing import Any

logger = logging.getLogger(__name__)

router = Router(name="seller.sales")


@router.message(F.text.in_({"💳 Продажа", "💳 Фурӯш"}))
async def start_sale(
    message: Message, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    await state.clear()
    order_svc = OrderService(session)
    items = await order_svc.get_store_inventory(user.store_id, include_empty=False)
    if not items:
        await message.answer(_("sale_no_products"))
        return
        
    available_items = [inv for inv in items if inv.quantity > 0]
    if not available_items:
        await message.answer(_("sale_no_available"))
        return

    await send_catalog_page(
        message,
        _("sale_title"),
        available_items,
        page=0,
        callback_prefix="sale:page",
        item_callback_prefix="sale:select",
        _=_,
    )
    await state.set_state(SaleFlow.select_product)


@router.message(SaleFlow.select_product, F.text)
async def sale_search_product(
    message: Message, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    if message.text.strip() in MENU_TEXTS:
        await state.clear()
        return

    order_svc = OrderService(session)
    items = await order_svc.get_store_inventory(user.store_id, include_empty=False)
    clean_query = clean_search_query(message.text)
    exact_match = next((item for item in items if clean_search_query(item.product.sku) == clean_query), None)
    matches = [item for item in items if product_matches(item.product, message.text)]

    if exact_match:
        await state.update_data(product_id=exact_match.product.id)
        await message.answer(
            product_card(exact_match.product, _, exact_match.quantity)
            + "\n\n"
            + _("sale_enter_qty", qty=exact_match.quantity),
            parse_mode="HTML",
        )
        await state.set_state(SaleFlow.enter_quantity)
        return
    elif matches:
        await send_catalog_page(
            message,
            _("sale_search_found"),
            matches,
            page=0,
            callback_prefix="sale:page",
            item_callback_prefix="sale:select",
            _=_,
        )
        return
    else:
        await message.answer(_("sale_not_found"))
        return


@router.callback_query(SaleFlow.select_product, F.data.startswith("sale:page:"))
async def sale_page_nav(
    callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    page = int(callback.data.split(":")[-1])
    
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
    await send_catalog_page(
        callback,
        _("sale_title"),
        list(items),
        page=page,
        callback_prefix="sale:page",
        item_callback_prefix="sale:select",
        _=_,
    )
    await callback.answer()


@router.callback_query(SaleFlow.select_product, F.data.startswith("sale:select:"))
async def sale_select_product(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, _: Any
) -> None:
    product_id = int(callback.data.split(":")[-1])
    
    from app.models.inventory import Inventory
    result = await session.execute(
        select(Inventory).where(Inventory.store_id == user.store_id, Inventory.product_id == product_id)
    )
    inv = result.scalar_one_or_none()
    qty = inv.quantity if inv else 0
    
    from app.models.product import Product
    product = await session.get(Product, product_id)
    await state.update_data(product_id=product_id)
    await callback.message.edit_text(
        (product_card(product, _, qty) + "\n\n" if product else "") + _("sale_enter_qty", qty=qty),
        parse_mode="HTML",
    )
    await state.set_state(SaleFlow.enter_quantity)
    await callback.answer()


@router.message(SaleFlow.enter_quantity)
async def enter_sale_quantity(
    message: Message, state: FSMContext, user: User, session: AsyncSession, _: Any
) -> None:
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer(_("sale_invalid_qty"))
        return

    quantity = int(message.text)
    data = await state.get_data()
    product_id = data.get("product_id")
    
    if not product_id:
        await message.answer(_("sale_select_first"))
        await state.clear()
        return

    try:
        from app.models.product import Product
        product = await session.get(Product, product_id)

        retail_price = product.effective_store_price

        txn_svc = TransactionService(session)
        await txn_svc.record_sale(
            store_id=user.store_id,
            user_id=user.id,
            product_id=product_id,
            quantity=quantity,
            price_per_unit=retail_price,
        )
        await session.commit()
        await message.answer(
            _("sale_success", sku=product.sku, qty=quantity)
        )
    except ValueError as e:
        await message.answer(_("sale_error", error=str(e)))
    except Exception as e:
        await message.answer(_("sale_system_error"))
        logger.exception("Error in enter_sale_quantity: %s", e)
    finally:
        await state.clear()


@router.message(F.text.in_({"📜 Продажи", "📜 Фурӯшҳо"}))
async def sales_history(
    message: Message, user: User, session: AsyncSession, state: FSMContext, _: Any
) -> None:
    await state.clear()
    txn_svc = TransactionService(session)
    rows = await txn_svc.get_store_sales(user.store_id, limit=10)

    if not rows:
        await message.answer(_("sales_history_empty"))
        return

    lines = [_("sales_history_title") + "\n"]
    for sale in rows:
        dt_str = sale.created_at.strftime("%d.%m %H:%M")
        amount = sale.total_amount
        lines.append(
            _("sales_history_item", date=dt_str, sku=sale.product.sku, qty=sale.quantity, amount=amount)
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data.startswith("order:sold:"))
async def quick_sold_order(
    callback: CallbackQuery, user: User, session: AsyncSession, _: Any
) -> None:
    order_id = int(callback.data.split(":")[-1])
    try:
        from app.models.order import Order
        from sqlalchemy.orm import selectinload
        order = await session.get(Order, order_id, options=[selectinload(Order.product)])
        if not order:
            await callback.answer(_("order_not_found"), show_alert=True)
            return

        txn_svc = TransactionService(session)
        await txn_svc.record_sale(
            store_id=user.store_id,
            user_id=user.id,
            product_id=order.product_id,
            quantity=order.quantity,
            price_per_unit=order.price_per_item,
            order_id=order_id,
        )
        await session.commit()
        await callback.message.edit_text(
            _("sale_quick_success", sku=order.product.sku, qty=order.quantity, total=order.price_per_item * order.quantity),
            parse_mode="HTML"
        )
    except ValueError as e:
        await callback.message.edit_text(_("sale_error", error=str(e)))
    except Exception as e:
        await callback.message.edit_text(_("sale_system_error"))
        logger.exception("Error in quick_sold_order: %s", e)
    finally:
        await callback.answer()
