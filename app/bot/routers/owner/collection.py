from decimal import Decimal, InvalidOperation
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import collection_amount_kb, stores_debt_kb
from app.bot.states.states import CashCollectionFlow
from app.models.store import Store
from app.models.user import User
from app.services import TransactionService

router = Router(name="owner.collection")


@router.message(F.text.in_({"💰 Сбор денег", "💰 Ҷамъоварии пул"}))
async def start_collection(
    message: Message, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    """Show list of stores that owe money."""
    await state.clear()
    txn_svc = TransactionService(session)
    stores = await txn_svc.get_stores_with_debt()
    
    if not stores:
        await message.answer(_("collect_no_debt"))
        return
        
    await message.answer(
        _("collect_title"),
        parse_mode="HTML",
        reply_markup=stores_debt_kb(stores, _=_),
    )
    await state.set_state(CashCollectionFlow.select_store)


@router.callback_query(
    CashCollectionFlow.select_store, F.data.startswith("collect:store:")
)
async def select_store(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, _: Any
) -> None:
    """Show store debt and collection options."""
    store_id = int(callback.data.split(":")[-1])
    
    # We fetch with lock to show the MOST accurate debt right now
    stmt = select(Store).where(Store.id == store_id).with_for_update()
    res = await session.execute(stmt)
    store = res.scalar_one_or_none()
    
    if not store:
        await callback.answer(_("collect_not_found"), show_alert=True)
        return

    # Store debt as STRING in FSM to avoid float precision issues
    await state.update_data(store_id=store_id, debt=str(store.current_debt))
    
    await callback.message.edit_text(
        _("collect_current_debt", name=store.name, address=store.address, debt=store.current_debt),
        parse_mode="HTML",
        reply_markup=collection_amount_kb(store_id, float(store.current_debt), _=_),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("collect:full:"))
async def collect_full(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, _: Any
) -> None:
    """Collect the ENTIRE current debt."""
    store_id = int(callback.data.split(":")[-1])
    
    # CRITICAL: We don't trust FSM data for 'full' collection. 
    # We fetch the latest debt from DB with lock.
    stmt = select(Store).where(Store.id == store_id).with_for_update()
    res = await session.execute(stmt)
    store = res.scalar_one_or_none()
    
    if not store or store.current_debt <= 0:
        await callback.message.edit_text(_("collect_full_error"))
        await state.clear()
        return

    amount = store.current_debt
    txn_svc = TransactionService(session)
    
    try:
        txn = await txn_svc.record_cash_collection(
            store_id, user.id, amount
        )
        await session.commit()
        
        await callback.message.edit_text(
            _("collect_full_success", name=store.name, amount=txn.amount),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(_("collect_system_error", error=str(e)))
        await session.rollback()
    finally:
        await state.clear()
        await callback.answer()


@router.callback_query(F.data.startswith("collect:partial:"))
async def collect_partial_start(
    callback: CallbackQuery, state: FSMContext, _: Any
) -> None:
    """Prompt for custom collection amount."""
    data = await state.get_data()
    store_id = data.get("store_id")
    await callback.message.edit_text(
        _("collect_partial_prompt")
    )
    await state.set_state(CashCollectionFlow.enter_amount)
    await callback.answer()


@router.message(CashCollectionFlow.enter_amount)
async def collect_partial_amount(
    message: Message, state: FSMContext, user: User, session: AsyncSession, _: Any
) -> None:
    """Process custom amount collection."""
    try:
        amount_str = message.text.strip().replace(",", ".")
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer(_("stock_invalid_qty"))
        return

    data = await state.get_data()
    store_id = data.get("store_id")

    # TransactionService handles the locking and debt checking
    txn_svc = TransactionService(session)
    try:
        txn = await txn_svc.record_cash_collection(
            store_id, user.id, amount
        )
        await session.commit()
        
        # Fetch updated store to show remaining debt
        store = await session.get(Store, store_id)
        
        await message.answer(
            _("collect_partial_success", amount=txn.amount, debt=store.current_debt),
            parse_mode="HTML"
        )
    except ValueError as e:
        await message.answer(f"❌ " + _("error_label") + f": {e}")
        await session.rollback()
    except Exception as e:
        await message.answer(_("collect_system_error", error=str(e)))
        print(f"Collection error: {e}")
        await session.rollback()
    finally:
        await state.clear()


@router.callback_query(F.data.startswith("collect:skip:"))
async def collect_skip(
    callback: CallbackQuery, state: FSMContext, _: Any
) -> None:
    await callback.message.edit_text(_("collect_skipped"))
    await state.clear()
    await callback.answer()
