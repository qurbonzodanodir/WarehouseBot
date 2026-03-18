from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrderStatus
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.product import Product


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_available_products(self, store_id: int) -> list[Product]:
        from app.services.store_service import StoreService
        from app.models.inventory import Inventory
        
        store_svc = StoreService(self.session)
        warehouse_id = await store_svc.get_main_warehouse_id()
        
        if not warehouse_id:
            return []

        # Alias for warehouse inventory to join twice
        from sqlalchemy.orm import aliased
        WhInventory = aliased(Inventory)
        StoreInventory = aliased(Inventory)

        stmt = (
            select(Product)
            .join(WhInventory, (Product.id == WhInventory.product_id) & (WhInventory.store_id == warehouse_id))
            .join(StoreInventory, (Product.id == StoreInventory.product_id) & (StoreInventory.store_id == store_id))
            .where(
                Product.is_active.is_(True),
                WhInventory.quantity > 0
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
        from app.models.inventory import Inventory
        res = await self.session.execute(
            select(Inventory).where(Inventory.store_id == store_id, Inventory.product_id == product_id)
        )
        if not res.scalar_one_or_none():
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
            warehouse_store_id, order.product_id
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
        Check if the batch can be fully fulfilled or only partially.
        Returns a dict with 'available', 'partial', and 'missing' lists of dictionaries.
        """
        orders = await self.get_batch_orders(batch_id)
        if not orders:
            raise ValueError(f"Batch #{batch_id} not found.")

        available = []
        partial = []
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

        return {"available": available, "partial": partial, "missing": missing, "orders": orders}

    async def create_adjusted_batch(
        self,
        batch_id: str,
        availability_data: dict,
    ) -> str:
        """
        Seller accepts partial fulfillment:
        Reject missing/partial remainders, return a new batch ID with available items as PENDING.
        """
        import uuid
        new_batch_id = uuid.uuid4().hex[:12]
        
        # Original orders from the availability dict
        available = availability_data["available"]
        partial = availability_data["partial"]
        missing = availability_data["missing"]
        
        # 1. Reject missing entirely
        for item in missing:
            order = item["order"]
            order.status = OrderStatus.REJECTED
            
        # 2. Split partial ones
        for item in partial:
            order = item["order"]
            available_qty = item["available_qty"]
            remainder_qty = order.quantity - available_qty
            
            # Reject original order as remainder
            order.status = OrderStatus.REJECTED
            order.quantity = remainder_qty
            order.total_price = order.price_per_item * remainder_qty
            
            # Create new order for available qty in new batch
            new_order = Order(
                store_id=order.store_id,
                product_id=order.product_id,
                quantity=available_qty,
                price_per_item=order.price_per_item,
                total_price=order.price_per_item * available_qty,
                status=OrderStatus.PENDING,
                batch_id=new_batch_id,
            )
            self.session.add(new_order)
            
        # 3. Move fully available ones to new batch
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
        
        # Reserve the proposed quantity by deducting it from warehouse
        inv.quantity -= proposed_quantity
        
        # Update the order to the proposed quantity
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

        order.status = OrderStatus.REJECTED
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
    ) -> Inventory:
        """Get an inventory row or create one with quantity=0."""
        stmt = select(Inventory).where(
            Inventory.store_id == store_id,
            Inventory.product_id == product_id,
        )
        result = await self.session.execute(stmt)
        inv = result.scalar_one_or_none()
        if inv is None:
            inv = Inventory(
                store_id=store_id, product_id=product_id, quantity=0
            )
            self.session.add(inv)
            await self.session.flush()
        return inv
