import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy import select

from app.models.order import Order
from app.models.enums import OrderStatus
from app.services.transaction_service import TransactionService
from app.core.config import settings

# Setup DB connection
engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

from app.models.store import Store

async def fix_orders():
    target_order_ids = [936, 937, 938]
    
    async with AsyncSessionLocal() as session:
        txn_svc = TransactionService(session)
        
        for order_id in target_order_ids:
            try:
                # Get the order with store and users loaded
                result = await session.execute(
                    select(Order).options(
                        joinedload(Order.store).joinedload(Store.users)
                    ).where(Order.id == order_id)
                )
                order = result.unique().scalar_one_or_none()
                if not order:
                    print(f"Order #{order_id} not found.")
                    continue
                    
                print(f"Processing Order #{order_id} - Current Status: {order.status}")
                
                if order.status != OrderStatus.DELIVERED:
                    print(f"  Skipping Order #{order_id}: Not in DELIVERED status.")
                    continue
                
                # Try to record the sale
                try:
                    user_id = order.store.users[0].id if order.store.users else None
                    if not user_id:
                        print(f"  Error: No users found for store {order.store.id}")
                        continue
                        
                    await txn_svc.record_sale(
                        store_id=order.store_id,
                        user_id=user_id,
                        product_id=order.product_id,
                        quantity=order.quantity,
                        price_per_unit=order.price_per_item,
                        order_id=order.id
                    )
                    
                    # Ensure the status is set to SOLD if record_sale didn't do it
                    order.status = OrderStatus.SOLD
                    await session.flush()
                    
                    print(f"  Success: Order #{order_id} is now SOLD.")
                except ValueError as e:
                    # Handle inventory issues if there are any
                    print(f"  ValueError: {e}")
                    if "Недостаточно товара на витрине" in str(e):
                        print(f"  Force selling Order #{order_id} due to missing inventory.")
                        # If inventory is missing, it means they might have sold it already, or it was double sold.
                        # Let's forcibly mark it as SOLD without doing the inventory checks.
                        # Actually wait, let's first see if it throws an error.
                        
            except Exception as e:
                print(f"  Error processing Order #{order_id}: {e}")
                
        # Commit all changes
        await session.commit()
        print("Done. Changes committed.")

if __name__ == "__main__":
    asyncio.run(fix_orders())
