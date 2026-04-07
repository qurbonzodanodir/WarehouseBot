from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.display_inventory import DisplayInventory
from app.models.enums import OrderStatus
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.product import Product


@dataclass
class VitrineItem:
    product: Product
    quantity: int
    regular_quantity: int = 0
    display_quantity: int = 0


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_available_products(self, store_id: int) -> list[Product]:
        from app.services.store_service import StoreService
        from sqlalchemy import exists, or_
        
        store_svc = StoreService(self.session)
        warehouse_id = await store_svc.get_main_warehouse_id()
        
        if not warehouse_id:
            return []

        # Alias for warehouse inventory to join twice
        from sqlalchemy.orm import aliased
        WhInventory = aliased(Inventory)
        StoreInventory = aliased(Inventory)
        StoreDisplayInventory = aliased(DisplayInventory)

        stmt = (
            select(Product)
            .join(WhInventory, (Product.id == WhInventory.product_id) & (WhInventory.store_id == warehouse_id))
            .where(
                Product.is_active.is_(True),
                WhInventory.quantity > 0,
                or_(
                    exists(
                        select(StoreInventory.id).where(
                            StoreInventory.product_id == Product.id,
                            StoreInventory.store_id == store_id,
                            StoreInventory.quantity > 0,
                        )
                    ),
                    exists(
                        select(StoreDisplayInventory.id).where(
                            StoreDisplayInventory.product_id == Product.id,
                            StoreDisplayInventory.store_id == store_id,
                            StoreDisplayInventory.quantity > 0,
                        )
                    ),
                ),
            )
            .order_by(Product.sku)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_store_inventory(
        self, store_id: int, include_empty: bool = False
    ) -> list[Inventory]:
        from sqlalchemy.orm import joinedload

        stmt = (
            select(Inventory)
            .options(joinedload(Inventory.product))
            .where(Inventory.store_id == store_id)
        )
        if not include_empty:
            stmt = stmt.where(Inventory.quantity > 0)
        
        stmt = stmt.order_by(Inventory.product_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_store_vitrine_inventory(
        self,
        store_id: int,
        include_empty: bool = False,
    ) -> list[VitrineItem]:
        from sqlalchemy.orm import joinedload

        regular_result = await self.session.execute(
            select(Inventory)
            .options(joinedload(Inventory.product))
            .where(Inventory.store_id == store_id)
        )
        display_result = await self.session.execute(
            select(DisplayInventory)
            .options(joinedload(DisplayInventory.product))
            .where(DisplayInventory.store_id == store_id)
        )

        merged: dict[int, VitrineItem] = {}

        for inv in regular_result.scalars().all():
            item = merged.get(inv.product_id)
            if item is None:
                item = VitrineItem(product=inv.product, quantity=0)
                merged[inv.product_id] = item
            item.regular_quantity = inv.quantity
            item.quantity += inv.quantity

        for inv in display_result.scalars().all():
            item = merged.get(inv.product_id)
            if item is None:
                item = VitrineItem(product=inv.product, quantity=0)
                merged[inv.product_id] = item
            item.display_quantity = inv.quantity
            item.quantity += inv.quantity

        items = sorted(merged.values(), key=lambda item: item.product.id)
        if not include_empty:
            items = [item for item in items if item.quantity > 0]
        return items

    async def get_store_vitrine_product_stock(
        self,
        store_id: int,
        product_id: int,
    ) -> tuple[int, int]:
        regular_result = await self.session.execute(
            select(Inventory.quantity).where(
                Inventory.store_id == store_id,
                Inventory.product_id == product_id,
            )
        )
        display_result = await self.session.execute(
            select(DisplayInventory.quantity).where(
                DisplayInventory.store_id == store_id,
                DisplayInventory.product_id == product_id,
            )
        )
        regular_qty = regular_result.scalar_one_or_none() or 0
        display_qty = display_result.scalar_one_or_none() or 0
        return regular_qty, display_qty

    async def create_order(
        self,
        store_id: int,
        product_id: int,
        quantity: int,
        batch_id: str | None = None,
    ) -> Order:
        product = await self.session.get(Product, product_id)
        if not product:
            raise ValueError(f"Product #{product_id} not found.")

        # EXTRA SECURITY: Check if product is in VITRINE
        regular_qty, display_qty = await self.get_store_vitrine_product_stock(store_id, product_id)
        if regular_qty <= 0 and display_qty <= 0:
            raise ValueError("order_must_be_in_vitrine")

        price = product.price
        total_price = price * quantity

        order = Order(
            store_id=store_id,
            product_id=product_id,
            quantity=quantity,
            price_per_item=price,
            total_price=total_price,
            status=OrderStatus.PENDING,
            batch_id=batch_id,
        )
        self.session.add(order)
        await self.session.flush()
        return order

    async def dispatch_order(
        self,
        order_id: int,
        warehouse_store_id: int,
    ) -> Order:
        order = await self.session.get(Order, order_id)
        if order is None or order.status != OrderStatus.PENDING:
            raise ValueError(f"Order #{order_id} is not in PENDING status.")

        # Deduct from warehouse inventory
        inv = await self._get_or_create_inventory(
            warehouse_store_id, order.product_id, lock=True
        )
        if inv.quantity < order.quantity:
            raise ValueError(
                f"Not enough stock: have {inv.quantity}, need {order.quantity}."
            )
        inv.quantity -= order.quantity

        from app.services.transaction_service import TransactionService
        from app.models.enums import StockMovementType
        
        txn_service = TransactionService(self.session)
        await txn_service.record_stock_movement(
            product_id=order.product_id, quantity=order.quantity,
            movement_type=StockMovementType.DISPATCH_TO_STORE,
            from_store_id=warehouse_store_id, to_store_id=order.store_id
        )

        order.status = OrderStatus.DISPATCHED
        await self.session.flush()
        return order

    async def get_batch_orders(self, batch_id: str) -> list[Order]:
        """Return all orders for a specific batch."""
        from sqlalchemy.orm import joinedload
        stmt = (
            select(Order)
            .options(joinedload(Order.store), joinedload(Order.product))
            .where(Order.batch_id == batch_id)
            .order_by(Order.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def check_batch_availability(
        self,
        batch_id: str,
        warehouse_store_id: int,
    ) -> dict:
        """
        Check whether each line in the batch is fully available.
        Current workflow only supports full fulfillment per line item:
        an item is either available in full or missing.
        """
        orders = await self.get_batch_orders(batch_id)
        if not orders:
            raise ValueError(f"Batch #{batch_id} not found.")

        available = []
        missing = []

        from app.models.enums import OrderStatus
        for order in orders:
            # We must check availability for both PENDING (initial warehouse check) 
            # and PARTIAL_APPROVAL_PENDING (seller verifying before creating new batch)
            if order.status in (OrderStatus.PENDING, OrderStatus.PARTIAL_APPROVAL_PENDING):
                inv = await self._get_or_create_inventory(warehouse_store_id, order.product_id)
                if inv.quantity < order.quantity:
                    # Treat partial stock as completely missing (seller doesn't want less than requested)
                    missing.append({"order": order, "available_qty": 0})
                else:
                    available.append({"order": order, "available_qty": order.quantity})

        return {"available": available, "partial": [], "missing": missing, "orders": orders}

    async def create_adjusted_batch(
        self,
        batch_id: str,
        availability_data: dict,
    ) -> str:
        """
        Seller accepts partial fulfillment:
        Reject missing items and move fully available ones into a new batch ID as PENDING.
        """
        import uuid
        new_batch_id = uuid.uuid4().hex[:12]
        
        # Original orders from the availability dict
        available = availability_data["available"]
        missing = availability_data["missing"]
        
        # 1. Reject missing entirely
        for item in missing:
            order = item["order"]
            order.status = OrderStatus.REJECTED
            
        # 2. Move fully available ones to new batch
        for item in available:
            order = item["order"]
            order.status = OrderStatus.PENDING
            order.batch_id = new_batch_id
            
        await self.session.flush()
        return new_batch_id


    async def dispatch_batch_order(
        self,
        batch_id: str,
        warehouse_store_id: int,
    ) -> list[Order]:
        """
        Strictly dispatch all PENDING items in the batch.
        Assumes it was already checked for full availability.
        Throws error if not available.
        """
        orders = await self.get_batch_orders(batch_id)
        if not orders:
            raise ValueError(f"Batch #{batch_id} not found.")

        dispatched_orders = []
        for order in orders:
            if order.status == OrderStatus.PENDING:
                inv = await self._get_or_create_inventory(
                    warehouse_store_id, order.product_id
                )
                
                if inv.quantity < order.quantity:
                    raise ValueError(f"Insufficient stock for SKU {order.product.sku}")

                # Deduct available qty
                inv.quantity -= order.quantity

                from app.services.transaction_service import TransactionService
                from app.models.enums import StockMovementType
                
                txn_service = TransactionService(self.session)
                await txn_service.record_stock_movement(
                    product_id=order.product_id, quantity=order.quantity,
                    movement_type=StockMovementType.DISPATCH_TO_STORE,
                    from_store_id=warehouse_store_id, to_store_id=order.store_id
                )

                order.status = OrderStatus.DISPATCHED
                dispatched_orders.append(order)
                
        await self.session.flush()
        return dispatched_orders

    async def reject_batch_order(
        self,
        batch_id: str,
    ) -> list[Order]:
        orders = await self.get_batch_orders(batch_id)
        if not orders:
            raise ValueError(f"Batch #{batch_id} not found.")

        for order in orders:
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.REJECTED
                
        await self.session.flush()
        return orders

    async def propose_partial_dispatch(
        self,
        order_id: int,
        warehouse_store_id: int,
        proposed_quantity: int,
    ) -> Order:
        order = await self.session.get(Order, order_id)
        if order is None or order.status != OrderStatus.PENDING:
            raise ValueError(f"Order #{order_id} is not in PENDING status.")

        inv = await self._get_or_create_inventory(
            warehouse_store_id, order.product_id
        )
        if inv.quantity < proposed_quantity:
            raise ValueError(
                f"Недостаточно товара: есть {inv.quantity}, предложено {proposed_quantity}."
            )

        original_quantity = order.quantity
        remainder = original_quantity - proposed_quantity
        import uuid
        partial_group_id = order.batch_id or f"partial-{uuid.uuid4().hex[:12]}"
        
        # Reserve the proposed quantity by deducting it from warehouse
        inv.quantity -= proposed_quantity
        
        # Update the order to the proposed quantity
        order.batch_id = partial_group_id
        order.quantity = proposed_quantity
        order.total_price = order.price_per_item * proposed_quantity
        order.status = OrderStatus.PARTIAL_APPROVAL_PENDING
        
        # Create a new order for the remainder
        if remainder > 0:
            remainder_order = Order(
                store_id=order.store_id,
                product_id=order.product_id,
                quantity=remainder,
                price_per_item=order.price_per_item,
                total_price=order.price_per_item * remainder,
                status=OrderStatus.PENDING,
                batch_id=partial_group_id,
            )
            self.session.add(remainder_order)
        
        await self.session.flush()
        return order

    async def accept_partial_dispatch(
        self,
        order_id: int,
        warehouse_store_id: int,
    ) -> Order:
        order = await self.session.get(Order, order_id)
        if order is None or order.status != OrderStatus.PARTIAL_APPROVAL_PENDING:
            raise ValueError(f"Order #{order_id} is not waiting for partial approval.")

        from app.services.transaction_service import TransactionService
        from app.models.enums import StockMovementType
        
        txn_service = TransactionService(self.session)
        await txn_service.record_stock_movement(
            product_id=order.product_id, quantity=order.quantity,
            movement_type=StockMovementType.DISPATCH_TO_STORE,
            from_store_id=warehouse_store_id, to_store_id=order.store_id
        )

        order.status = OrderStatus.DISPATCHED
        await self.session.flush()
        return order

    async def reject_partial_dispatch(
        self,
        order_id: int,
        warehouse_store_id: int,
    ) -> Order:
        order = await self.session.get(Order, order_id)
        if order is None or order.status != OrderStatus.PARTIAL_APPROVAL_PENDING:
            raise ValueError(f"Order #{order_id} is not waiting for partial approval.")

        # Return reserved inventory to warehouse
        inv = await self._get_or_create_inventory(
            warehouse_store_id, order.product_id
        )
        inv.quantity += order.quantity

        if order.batch_id:
            sibling_stmt = (
                select(Order)
                .where(
                    Order.batch_id == order.batch_id,
                    Order.store_id == order.store_id,
                    Order.product_id == order.product_id,
                    Order.status == OrderStatus.PENDING,
                    Order.id != order.id,
                )
                .order_by(Order.created_at.desc())
            )
            sibling_result = await self.session.execute(sibling_stmt)
            sibling = sibling_result.scalars().first()
            if sibling:
                sibling.quantity += order.quantity
                sibling.total_price = sibling.price_per_item * sibling.quantity
                if sibling.batch_id.startswith("partial-"):
                    sibling.batch_id = None
                order.status = OrderStatus.REJECTED
                await self.session.flush()
                return sibling

        order.status = OrderStatus.REJECTED
        if order.batch_id and order.batch_id.startswith("partial-"):
            order.batch_id = None
            order.status = OrderStatus.PENDING
        await self.session.flush()
        return order

    async def deliver_order(
        self,
        order_id: int,
    ) -> Order:
        """
        Seller accepts delivery.
        - Add quantity to the store's inventory.
        - Set order status to DELIVERED.
        """
        order = await self.session.get(Order, order_id)
        if order is None or order.status != OrderStatus.DISPATCHED:
            raise ValueError(f"Order #{order_id} is not in DISPATCHED status.")

        # Credit to store inventory
        inv = await self._get_or_create_inventory(
            order.store_id, order.product_id
        )
        inv.quantity += order.quantity

        # StockMovement is already recorded as DISPATCH_TO_STORE in dispatch_order.
        # We don't need to record a second one here (Point 8 fix).
        
        order.status = OrderStatus.DELIVERED
        await self.session.flush()
        return order

    async def reject_order(
        self,
        order_id: int,
    ) -> Order:
        """Warehouse or seller rejects the order."""
        from sqlalchemy.orm import joinedload
        order = await self.session.get(Order, order_id, options=[joinedload(Order.product)])
        if order is None:
            raise ValueError(f"Order #{order_id} not found.")
        order.status = OrderStatus.REJECTED
        await self.session.flush()
        return order

    async def get_pending_orders(self) -> list[Order]:
        """Return all pending orders (for warehouse view)."""
        from sqlalchemy.orm import joinedload

        stmt = (
            select(Order)
            .options(joinedload(Order.store), joinedload(Order.product))
            .where(Order.status == OrderStatus.PENDING)
            .order_by(Order.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_dispatched_orders_for_store(
        self, store_id: int
    ) -> list[Order]:
        """Return dispatched (in-transit) orders for a specific store."""
        from sqlalchemy.orm import joinedload

        stmt = (
            select(Order)
            .options(joinedload(Order.product))
            .where(
                Order.store_id == store_id,
                Order.status == OrderStatus.DISPATCHED,
            )
            .order_by(Order.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    async def _get_or_create_inventory(
        self,
        store_id: int,
        product_id: int,
        lock: bool = False,
    ) -> Inventory:
        """Get an inventory row or create one with quantity=0."""
        stmt = select(Inventory).where(
            Inventory.store_id == store_id,
            Inventory.product_id == product_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        inv = result.scalar_one_or_none()
        if inv is None:
            inv = Inventory(
                store_id=store_id, product_id=product_id, quantity=0
            )
            self.session.add(inv)
            await self.session.flush()
        return inv
