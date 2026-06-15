import asyncio
import sys
from decimal import Decimal
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.store import Store
from app.services.transaction_service import TransactionService
from app.models.enums import StockMovementType, DebtLedgerReason

async def main():
    commit = "--commit" in sys.argv
    print(f"Starting Aksiya brand move. Mode: {'COMMIT' if commit else 'DRY RUN'}")

    async with async_session_factory() as session:
        # 1. Fetch store info
        store_from_stmt = select(Store).where(Store.id == 1)
        store_to_stmt = select(Store).where(Store.id == 7)
        
        store_from = (await session.execute(store_from_stmt)).scalar_one_or_none()
        store_to = (await session.execute(store_to_stmt)).scalar_one_or_none()
        
        if not store_from:
            print("Error: Main Warehouse (store_id=1) not found.")
            return
        if not store_to:
            print("Error: Nekruz store (store_id=7) not found.")
            return
            
        print(f"Source Store: {store_from.name} (id={store_from.id})")
        print(f"Target Store: {store_to.name} (id={store_to.id}), Current Debt: {store_to.current_debt} TJS")

        # 2. Fetch inventory for brand "Акция"
        stmt = (
            select(Inventory, Product)
            .join(Product, Inventory.product_id == Product.id)
            .where(Product.brand == 'Акция', Inventory.store_id == 1, Inventory.quantity > 0)
            .order_by(Product.sku)
        )
        res = await session.execute(stmt)
        rows = res.all()
        
        if not rows:
            print("No active inventory found for brand 'Акция' on the Main Warehouse.")
            return
            
        print(f"Found {len(rows)} products with brand 'Акция' on Main Warehouse.")
        
        txn_svc = TransactionService(session)
        
        total_qty = 0
        total_value = Decimal("0.00")
        
        for inv, prod in rows:
            qty = inv.quantity
            price = prod.effective_store_price
            val = price * qty
            total_qty += qty
            total_value += val
            
            print(f"SKU: {prod.sku:<8} | Qty: {qty:<3} | Price: {price:<6} | Total Value: {val:<8}")
            
            if commit:
                # Decrement from warehouse
                inv.quantity = 0
                
                # Increment at target store
                inv_to = await txn_svc._get_or_create_inventory(store_to.id, prod.id, lock=True)
                inv_to.quantity += qty
                
                # Record stock movement
                await txn_svc.record_stock_movement(
                    product_id=prod.id,
                    quantity=qty,
                    movement_type=StockMovementType.DISPATCH_TO_STORE,
                    from_store_id=store_from.id,
                    to_store_id=store_to.id
                )
                
                # Record debt ledger entry
                await txn_svc.record_debt_ledger(
                    store_id=store_to.id,
                    amount_change=val,
                    reason=DebtLedgerReason.DELIVERY_ACCEPTED,
                    description=f"Перенос товара {prod.sku} ({qty} шт.) с Главного Склада (Акция)"
                )
                
        print("-" * 50)
        print(f"Total Items to Move: {total_qty}")
        print(f"Total Wholesale Value: {total_value} TJS")
        
        if commit:
            await session.commit()
            print("Transaction committed successfully!")
            
            # Refresh target store to show new debt
            await session.refresh(store_to)
            print(f"New Debt for Nekruz store: {store_to.current_debt} TJS")
        else:
            print("DRY RUN completed. No changes were saved. Run with --commit to apply changes.")

if __name__ == "__main__":
    asyncio.run(main())
