from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.enums import (
    DebtLedgerReason,
    FinancialTransactionType,
    StockMovementType,
)
from app.models.display_inventory import DisplayInventory
from app.models.inventory import Inventory
from app.models.sale import Sale
from app.models.store import Store
from app.models.stock_movement import StockMovement
from app.models.financial_transaction import FinancialTransaction
from app.models.debt_ledger import DebtLedger


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Core Helper Functions ---

    async def record_stock_movement(
        self,
        product_id: int,
        quantity: int,
        movement_type: StockMovementType,
        from_store_id: int | None = None,
        to_store_id: int | None = None,
        user_id: int | None = None,
    ) -> StockMovement:
        movement = StockMovement(
            product_id=product_id,
            from_store_id=from_store_id,
            to_store_id=to_store_id,
            quantity=quantity,
            movement_type=movement_type,
            user_id=user_id,
        )
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def record_financial_transaction(
        self,
        store_id: int,
        user_id: int,
        amount: Decimal,
        txn_type: FinancialTransactionType,
    ) -> FinancialTransaction:
        txn = FinancialTransaction(
            store_id=store_id,
            user_id=user_id,
            type=txn_type,
            amount=amount,
        )
        self.session.add(txn)
        await self.session.flush()
        return txn

    async def record_sale_entry(
        self,
        store_id: int,
        user_id: int,
        product_id: int,
        quantity: int,
        price_per_item: Decimal,
        order_id: int | None = None,
    ) -> Sale:
        sale = Sale(
            store_id=store_id,
            user_id=user_id,
            product_id=product_id,
            order_id=order_id,
            quantity=quantity,
            price_per_item=price_per_item,
            total_amount=price_per_item * quantity,
        )
        self.session.add(sale)
        await self.session.flush()
        return sale

    async def record_debt_ledger(
        self,
        store_id: int,
        amount_change: Decimal,
        reason: DebtLedgerReason,
        description: str | None = None,
    ) -> DebtLedger:
        # Lock the store record to prevent race conditions in debt calculation
        stmt = select(Store).where(Store.id == store_id).with_for_update()
        res = await self.session.execute(stmt)
        store = res.scalar_one_or_none()
        
        if not store:
            raise ValueError(f"Store {store_id} not found")

        new_balance = store.current_debt + amount_change
        if new_balance < 0:
            # We allow small rounding differences but not negative debt usually
            if abs(new_balance) < 0.01:
                new_balance = Decimal("0")
            else:
                raise ValueError(
                    f"Нельзя уменьшить долг ниже нуля. Баланс: {store.current_debt}, Изменение: {amount_change}"
                )

        store.current_debt = new_balance
        balance_after = new_balance

        ledger = DebtLedger(
            store_id=store_id,
            amount_change=amount_change,
            balance_after=balance_after,
            reason=reason,
            description=description,
        )
        self.session.add(ledger)
        await self.session.flush()
        return ledger

    # --- Business Logic Functions ---

    async def record_sale(
        self,
        store_id: int,
        user_id: int,
        product_id: int,
        quantity: int,
        price_per_unit: Decimal,
        order_id: int = None,
    ) -> FinancialTransaction:
        effective_price = price_per_unit

        # CRITICAL: Lock inventory row to prevent race conditions (double selling)
        inv = await self._get_inventory(store_id, product_id, lock=True)
        if inv is None or inv.quantity < quantity:
            available = inv.quantity if inv else 0
            raise ValueError(
                f"Недостаточно товара на витрине: в наличии {available}, нужно {quantity}."
            )

        if order_id is not None:
            from app.models.order import Order
            from app.models.enums import OrderStatus
            # Lock the order to prevent concurrent processing
            stmt = select(Order).where(Order.id == order_id).with_for_update()
            res = await self.session.execute(stmt)
            order = res.scalar_one_or_none()
            
            if order:
                if order.status != OrderStatus.DELIVERED:
                    raise ValueError("Заявка уже обработана (продана или возвращена).")
                order.status = OrderStatus.SOLD
                effective_price = order.price_per_item

        amount = effective_price * quantity

        # Deduct inventory
        inv.quantity -= quantity

        # 1. Record stock movement
        await self.record_stock_movement(
            product_id, quantity, StockMovementType.SALE,
            from_store_id=store_id, to_store_id=None, user_id=user_id
        )

        # 2. Record financial transaction
        txn = await self.record_financial_transaction(
            store_id, user_id, amount, FinancialTransactionType.PAYMENT
        )

        # 3. Record sale snapshot
        await self.record_sale_entry(
            store_id=store_id,
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            price_per_item=effective_price,
            order_id=order_id,
        )

        # 4. Increase debt
        await self.record_debt_ledger(
            store_id, amount, DebtLedgerReason.SALE_COMPLETED,
            description=f"Продажа {quantity} шт. (Заявка {order_id if order_id else 'Витрина'})"
        )

        return txn

    async def initiate_return(
        self,
        store_id: int,
        user_id: int,
        product_id: int,
        quantity: int,
        order_id: int,
    ) -> None:
        """
        Step 1: Seller initiates a return.
        - LOCKS and deducts quantity from the store inventory.
        """
        from app.models.order import Order
        from app.models.enums import OrderStatus
        
        # Lock order
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        res = await self.session.execute(stmt)
        order = res.scalar_one_or_none()
        
        if order:
            allowed = (OrderStatus.DELIVERED, OrderStatus.RETURN_PENDING, OrderStatus.DISPLAY_RETURN_PENDING)
            if order.status not in allowed:
                raise ValueError(f"Заявка #{order_id} уже в статусе {order.status}, возврат невозможен.")

        is_display_return = order.status == OrderStatus.DISPLAY_RETURN_PENDING
        if is_display_return:
            inv = await self._get_display_inventory(store_id, product_id, lock=True)
            if inv is None or inv.quantity < quantity:
                available = inv.quantity if inv else 0
                raise ValueError(f"Недостаточно образцов для возврата: в наличии {available}, нужно {quantity}.")
        else:
            inv = await self._get_inventory(store_id, product_id, lock=True)
            if inv is None or inv.quantity < quantity:
                available = inv.quantity if inv else 0
                raise ValueError(f"Недостаточно товара для возврата: в наличии {available}, нужно {quantity}.")

        inv.quantity -= quantity
        await self.session.flush()

    async def approve_return(
        self,
        warehouse_store_id: int,
        warehouse_user_id: int,
        order_id: int,
    ) -> StockMovement:
        """
        Step 2: Warehouse approves.
        """
        from app.models.order import Order
        from app.models.enums import OrderStatus
        from app.models.product import Product
        
        # Lock order
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        res = await self.session.execute(stmt)
        order = res.scalar_one_or_none()
        
        if order is None or order.status not in (OrderStatus.RETURN_PENDING, OrderStatus.DISPLAY_RETURN_PENDING):
            raise ValueError("Некорректный статус заявки для одобрения возврата.")

        is_display_return = order.status == OrderStatus.DISPLAY_RETURN_PENDING
        product = await self.session.get(Product, order.product_id)
        price_to_use = order.price_per_item if order.price_per_item > 0 else product.price
        amount = price_to_use * order.quantity

        # Credit inventory to Warehouse WITH LOCK
        inv = await self._get_or_create_inventory(warehouse_store_id, order.product_id, lock=True)
        inv.quantity += order.quantity

        order.status = OrderStatus.DISPLAY_RETURNED if is_display_return else OrderStatus.RETURNED

        # 1. Record stock movement
        mov_type = StockMovementType.DISPLAY_RETURN if is_display_return else StockMovementType.RETURN_TO_WAREHOUSE
        mov = await self.record_stock_movement(
            order.product_id, order.quantity, mov_type,
            from_store_id=order.store_id, to_store_id=warehouse_store_id, user_id=warehouse_user_id
        )

        # 2. Record Debt Reduction (CRITICAL FIX)
        # If it's a regular item return, we MUST reduce the store's debt.
        if not is_display_return:
            # Calculate amount from the order's fixed price
            amount = order.price_per_item * order.quantity
            if amount > 0:
                await self.record_debt_ledger(
                    store_id=order.store_id,
                    amount_change=-amount,  # Negative means debt reduction
                    reason=DebtLedgerReason.RETURN_APPROVED,
                    description=f"Возврат товара #{order.id} на склад (SKU: {product.sku}, {order.quantity} шт.)"
                )

        return mov

    async def reject_return(
        self,
        order_id: int,
    ) -> None:
        """
        Step 2: Warehouse rejects.
        """
        from app.models.order import Order
        from app.models.enums import OrderStatus
        
        # Lock order
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        res = await self.session.execute(stmt)
        order = res.scalar_one_or_none()
        
        if order is None or order.status not in (OrderStatus.RETURN_PENDING, OrderStatus.DISPLAY_RETURN_PENDING):
            raise ValueError("Некорректный статус заявки для отклонения возврата.")

        is_display = order.status == OrderStatus.DISPLAY_RETURN_PENDING

        # Put inventory back WITH LOCK
        if is_display:
            inv = await self._get_or_create_display_inventory(order.store_id, order.product_id, lock=True)
        else:
            inv = await self._get_or_create_inventory(order.store_id, order.product_id, lock=True)
        inv.quantity += order.quantity

        order.status = OrderStatus.DISPLAY_DELIVERED if is_display else OrderStatus.DELIVERED
        await self.session.flush()

    async def record_cash_collection(
        self,
        store_id: int,
        admin_user_id: int,
        amount: Decimal,
    ) -> FinancialTransaction:
        """
        Admin collects cash.
        """
        txn = await self.record_financial_transaction(
            store_id, admin_user_id, amount, FinancialTransactionType.COLLECTION
        )
        await self.record_debt_ledger(
            store_id, -amount, DebtLedgerReason.CASH_COLLECTION,
            description=f"Инкассация наличных (Админ #{admin_user_id})"
        )
        return txn

    async def get_inventory(
        self,
        store_id: int,
        product_id: int,
        *,
        lock: bool = False,
    ) -> Inventory | None:
        return await self._get_inventory(store_id, product_id, lock=lock)

    async def receive_stock(
        self,
        warehouse_store_id: int,
        product_id: int,
        quantity: int,
        user_id: int,
    ) -> Inventory:
        inv = await self._get_or_create_inventory(warehouse_store_id, product_id, lock=True)
        inv.quantity += quantity
        await self.record_stock_movement(
            product_id=product_id,
            quantity=quantity,
            movement_type=StockMovementType.RECEIVE_FROM_SUPPLIER,
            to_store_id=warehouse_store_id,
            user_id=user_id,
        )
        await self.session.flush()
        return inv

    async def dispatch_display_items(
        self,
        warehouse_store_id: int,
        target_store_id: int,
        product_id: int,
        quantity: int,
        user_id: int,
    ):
        from app.models.order import Order
        from app.models.enums import OrderStatus

        wh_inv = await self._get_or_create_inventory(warehouse_store_id, product_id, lock=True)
        if wh_inv.quantity < quantity:
            raise ValueError(
                f"Недостаточно на складе: есть {wh_inv.quantity}, нужно {quantity}."
            )

        wh_inv.quantity -= quantity

        display_order = Order(
            store_id=target_store_id,
            product_id=product_id,
            quantity=quantity,
            price_per_item=Decimal("0"),
            total_price=Decimal("0"),
            status=OrderStatus.DISPLAY_DISPATCHED,
        )
        self.session.add(display_order)
        await self.session.flush()

        await self.record_stock_movement(
            product_id=product_id,
            quantity=quantity,
            movement_type=StockMovementType.DISPLAY_DISPATCH,
            from_store_id=warehouse_store_id,
            to_store_id=target_store_id,
            user_id=user_id,
        )
        await self.session.flush()
        return display_order, wh_inv

    async def _get_inventory(
        self, store_id: int, product_id: int, lock: bool = False
    ) -> Inventory | None:
        stmt = select(Inventory).where(
            Inventory.store_id == store_id,
            Inventory.product_id == product_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_display_inventory(
        self, store_id: int, product_id: int, lock: bool = False
    ) -> DisplayInventory | None:
        stmt = select(DisplayInventory).where(
            DisplayInventory.store_id == store_id,
            DisplayInventory.product_id == product_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_or_create_inventory(
        self, store_id: int, product_id: int, lock: bool = False
    ) -> Inventory:
        inv = await self._get_inventory(store_id, product_id, lock=lock)
        if inv is None:
            inv = Inventory(
                store_id=store_id, product_id=product_id, quantity=0
            )
            self.session.add(inv)
            await self.session.flush()
            # If we just created it and need a lock, we might need a refresh, 
            # but in Postgres flush is usually enough for the session.
        return inv

    async def _get_or_create_display_inventory(
        self, store_id: int, product_id: int, lock: bool = False
    ) -> DisplayInventory:
        inv = await self._get_display_inventory(store_id, product_id, lock=lock)
        if inv is None:
            inv = DisplayInventory(
                store_id=store_id, product_id=product_id, quantity=0
            )
            self.session.add(inv)
            await self.session.flush()
        return inv

    # (rest of the methods: get_store_financial_transactions, etc.)
    async def get_store_financial_transactions(
        self,
        store_id: int,
        limit: int = 20,
    ) -> list[FinancialTransaction]:
        stmt = (
            select(FinancialTransaction)
            .options(joinedload(FinancialTransaction.user))
            .where(FinancialTransaction.store_id == store_id)
            .order_by(FinancialTransaction.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_store_sales(
        self,
        store_id: int,
        limit: int = 20,
    ) -> list[Sale]:
        stmt = (
            select(Sale)
            .options(joinedload(Sale.product))
            .where(Sale.store_id == store_id)
            .order_by(Sale.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_stores_with_debt(self) -> list[Store]:
        stmt = (
            select(Store)
            .where(Store.is_active.is_(True), Store.current_debt > 0)
            .order_by(Store.current_debt.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def receive_display_items(self, order_id: int) -> None:
        from app.models.order import Order
        from app.models.enums import OrderStatus
        # Lock order
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        res = await self.session.execute(stmt)
        order = res.scalar_one_or_none()
        
        if order is None or order.status != OrderStatus.DISPLAY_DISPATCHED:
            raise ValueError("Некорректный статус для приемки образцов.")

        inv = await self._get_or_create_display_inventory(order.store_id, order.product_id, lock=True)
        inv.quantity += order.quantity
        order.status = OrderStatus.DISPLAY_DELIVERED
        
        await self.record_stock_movement(
            product_id=order.product_id, quantity=order.quantity,
            movement_type=StockMovementType.DISPLAY_RECEIVE,
            to_store_id=order.store_id
        )
        await self.session.flush()

    async def reject_display_items(
        self,
        order_id: int,
        warehouse_store_id: int,
        user_id: int | None = None,
    ) -> None:
        from app.models.order import Order
        from app.models.enums import OrderStatus

        stmt = select(Order).where(Order.id == order_id).with_for_update()
        res = await self.session.execute(stmt)
        order = res.scalar_one_or_none()

        if order is None or order.status != OrderStatus.DISPLAY_DISPATCHED:
            raise ValueError("Некорректный статус для отклонения образцов.")

        wh_inv = await self._get_or_create_inventory(warehouse_store_id, order.product_id, lock=True)
        wh_inv.quantity += order.quantity
        order.status = OrderStatus.DISPLAY_REJECTED

        await self.record_stock_movement(
            product_id=order.product_id,
            quantity=order.quantity,
            movement_type=StockMovementType.DISPLAY_RETURN,
            from_store_id=order.store_id,
            to_store_id=warehouse_store_id,
            user_id=user_id,
        )
        await self.session.flush()
