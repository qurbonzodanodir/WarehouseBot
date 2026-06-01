import logging
from html import escape
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
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

    cart = data.get("cart", [])
    product_names = data.get("product_names", {})
    
    found = False
    for item in cart:
        if item["product_id"] == product_id:
            item["qty"] += quantity
            found = True
            break
            
    if not found:
        cart.append({"product_id": product_id, "sku": product.sku, "qty": quantity})
        
    from app.bot.routers.seller.catalog_ui import _brand
    product_names[str(product_id)] = f"{product.sku} / {_brand(product)}"
        
    await state.update_data(cart=cart, product_names=product_names)
    
    items_text = "\n".join([f"• {product_names.get(str(i['product_id']), i['sku'])} — {i['qty']} шт" for i in cart])
    
    from app.bot.keyboards.inline import customer_return_cart_action_kb
    await message.answer(
        _("cart_status", items=items_text),
        parse_mode="HTML",
        reply_markup=customer_return_cart_action_kb(_=_)
    )
    await state.set_state(CustomerReturnFlow.cart_action)


@router.callback_query(CustomerReturnFlow.cart_action, F.data == "customer_return_cart:add_more")
async def customer_return_cart_add_more(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await callback.message.edit_text(_("customer_return_prompt"), parse_mode="HTML")
    await state.set_state(CustomerReturnFlow.enter_sku)
    await callback.answer()


@router.callback_query(CustomerReturnFlow.cart_action, F.data == "customer_return_cart:clear")
async def customer_return_cart_clear(callback: CallbackQuery, state: FSMContext, _: Any) -> None:
    await state.update_data(cart=[])
    await callback.message.edit_text(_("cart_cleared"))
    await state.clear()
    await callback.answer()


@router.callback_query(CustomerReturnFlow.cart_action, F.data == "customer_return_cart:send")
async def customer_return_cart_send(
    callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    from app.bot.keyboards.inline import warehouse_return_kb
    from app.services.notification_service import NotificationService
    
    data = await state.get_data()
    cart = data.get("cart", [])
    if not cart:
        await callback.message.edit_text(_("cart_cleared"))
        await state.clear()
        return

    txn_svc = TransactionService(session)
    notif_svc = NotificationService(callback.bot, session)
    
    try:
        for item in cart:
            order_id = await txn_svc.record_customer_return_and_dispatch(
                store_id=user.store_id,
                user_id=user.id,
                product_id=item["product_id"],
                quantity=item["qty"],
            )
            
            # Send notification to warehouse for each item
            await notif_svc.notify_warehouse(
                text=lambda _t, oid=order_id, sku=item["sku"], qty=item["qty"]: _t(
                    "return_notif_wh",
                    type=_t("return_type_goods"),
                    store=user.store.name if user.store and user.store.name else _t("store_label"),
                    id=oid,
                    sku=sku,
                    qty=qty,
                    note=_t("return_notif_wh_instr")
                ),
                reply_markup=lambda _t, oid=order_id: warehouse_return_kb(oid, _=_t)
            )
            
        await session.commit()
        await callback.message.edit_text(_("customer_return_success"), parse_mode="HTML")
        
    except Exception as e:
        await session.rollback()
        logger.exception("Error processing customer return cart: %s", e)
        await callback.message.edit_text(_("sale_system_error"))
    finally:
        await state.clear()
        await callback.answer()
