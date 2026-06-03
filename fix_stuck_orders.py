import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.order import Order
from app.models.enums import OrderStatus
from app.services.order_service import OrderService
from app.services.transaction_service import TransactionService
from app.models.user import User

async def main():
    async with async_session_factory() as session:
        stmt = select(Order).where(
            Order.status.in_([OrderStatus.DISPATCHED, OrderStatus.DELIVERED]),
            Order.created_at >= datetime(2026, 5, 31, tzinfo=timezone.utc)
        ).order_by(Order.id)
        
        result = await session.execute(stmt)
        orders = result.scalars().all()
        
        print(f"Found {len(orders)} orders to fix.")
        
        order_svc = OrderService(session)
        txn_svc = TransactionService(session)
        
        fixed_count = 0
        error_orders = []
        for order in orders:
            try:
                user_stmt = select(User).where(User.store_id == order.store_id).limit(1)
                user_res = await session.execute(user_stmt)
                user = user_res.scalar_one_or_none()
                if not user:
                    print(f"No user found for store {order.store_id}, skipping order {order.id}")
                    continue
                
                order_id = order.id
                order_status = order.status
                print(f"Processing order {order_id} with status {order_status.value}...")
                
                if order_status == OrderStatus.DISPATCHED:
                    # 1. Accept delivery
                    await order_svc.deliver_order(order_id)
                    await session.flush()
                
                # 2. Record sale
                try:
                    await txn_svc.record_sale(
                        store_id=order.store_id,
                        user_id=user.id,
                        product_id=order.product_id,
                        quantity=order.quantity,
                        price_per_unit=order.price_per_item,
                        order_id=order_id
                    )
                except ValueError as e:
                    if "Недостаточно товара на витрине" in str(e):
                        print(f"Order {order_id} doesn't have enough inventory. Forcing status to SOLD.")
                        db_order = await session.get(Order, order_id)
                        db_order.status = OrderStatus.SOLD
                    else:
                        raise e
                
                await session.commit()
                print(f"Order {order_id} fixed successfully!")
                fixed_count += 1
                
            except Exception as e:
                await session.rollback()
                print(f"Failed to fix order {order.id}: {e}")
                error_orders.append(order.id)
                
        print(f"Successfully fixed {fixed_count} orders!")
        print(f"Failed to fix {len(error_orders)} orders: {error_orders}")

if __name__ == "__main__":
    asyncio.run(main())
