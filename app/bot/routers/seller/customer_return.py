import logging
from html import escape
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.bot.states.states import CustomerReturnFlow
from app.models.user import User
from app.models.product import Product
from app.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

router = Router(name="seller.customer_return")


@router.message(F.text.in_({"🔄 Возврат от клиента", "🔄 Бозгашт аз муштарӣ"}))
async def start_customer_return(
    message: Message, user: User, state: FSMContext, _: Any
) -> None:
    await state.clear()
    await message.answer(_("customer_return_prompt"), parse_mode="HTML")
    await state.set_state(CustomerReturnFlow.enter_sku)


@router.message(CustomerReturnFlow.enter_sku, F.text)
async def process_customer_return_sku(
    message: Message, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    sku = message.text.strip()
    
    # Check if a product with this SKU exists
    stmt = select(Product).where(Product.sku == sku)
    res = await session.execute(stmt)
    product = res.scalar_one_or_none()

    if not product or product.price <= 0:
        await message.answer(_("customer_return_not_found"))
        return

    await state.update_data(product_id=product.id)
    await message.answer(_("customer_return_qty", sku=escape(product.sku)), parse_mode="HTML")
    await state.set_state(CustomerReturnFlow.enter_quantity)


@router.message(CustomerReturnFlow.enter_quantity, F.text)
async def process_customer_return_quantity(
    message: Message, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer(_("sale_invalid_qty"))
        return

    quantity = int(message.text)
    data = await state.get_data()
    product_id = data.get("product_id")

    if not product_id:
        await state.clear()
        return

    from app.models.product import Product
    product = await session.get(Product, product_id)
    if not product:
        await state.clear()
        return

    txn_svc = TransactionService(session)
    
    try:
        order_id = await txn_svc.record_customer_return_and_dispatch(
            store_id=user.store_id,
            user_id=user.id,
            product_id=product_id,
            quantity=quantity,
        )
        await session.commit()
        await message.answer(_("customer_return_success"), parse_mode="HTML")
        
        # Send notification to warehouse
        from app.services.notification_service import NotificationService
        from app.bot.keyboards.inline import get_return_approval_keyboard
        
        notif_svc = NotificationService(message.bot, session)
        await notif_svc.notify_warehouse(
            text=lambda _t: _t(
                "return_notif_wh",
                type=_t("return_type_goods"),
                store=user.store.name if user.store and user.store.name else _t("store_label"),
                id=order_id,
                sku=product.sku,
                qty=quantity,
                note=_t("return_notif_wh_instr")
            ),
            reply_markup=lambda _t: get_return_approval_keyboard(_t, order_id, is_display=False)
        )
    except Exception as e:
        logger.exception("Error processing customer return: %s", e)
        await message.answer(_("sale_system_error"))
    finally:
        await state.clear()
