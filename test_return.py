import asyncio
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.enums import FinancialTransactionType, OrderStatus
from app.models.product import Product
from app.models.order import Order
from app.models.sale import Sale
from app.models.financial_transaction import FinancialTransaction
from app.services.transaction_service import TransactionService

# Using production DB string to test (we will rollback)
DATABASE_URL = "postgresql+asyncpg://postgres:rz7r-Z@PzCbK9K@176.124.200.114:5432/warehouse"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

async def test_customer_return():
    async with AsyncSessionLocal() as session:
        # Start a transaction we will roll back
        async with session.begin_nested() as nested_txn:
            try:
                # 1. Fetch real product to test with
                from sqlalchemy import select
                res = await session.execute(select(Product).limit(1))
                product = res.scalar_one_or_none()
                if not product:
                    print("No product found.")
                    return
                
                print(f"Testing with Product ID {product.id}, SKU {product.sku}, Wholesale Price {product.price}, Effective Price {product.effective_store_price}")

                store_id = 4 # Nekruz
                user_id = 14 # Nekruz user
                quantity = 2

                txn_svc = TransactionService(session)
                order_id = await txn_svc.record_customer_return_and_dispatch(
                    store_id=store_id,
                    user_id=user_id,
                    product_id=product.id,
                    quantity=quantity
                )
                await session.flush()
                
                print(f"Order ID created: {order_id}")

                # Verify Order
                order_res = await session.execute(select(Order).where(Order.id == order_id))
                order = order_res.scalar_one()
                assert order.status == OrderStatus.RETURN_PENDING, f"Expected RETURN_PENDING, got {order.status}"
                assert order.quantity == quantity, f"Expected quantity {quantity}, got {order.quantity}"
                assert order.price_per_item == product.price, f"Expected order price {product.price}, got {order.price_per_item}"
                print("Order verification passed.")

                # Verify Sale
                sale_res = await session.execute(select(Sale).where(Sale.user_id == user_id).order_by(Sale.id.desc()).limit(1))
                sale = sale_res.scalar_one()
                assert sale.quantity == -quantity, f"Expected sale quantity {-quantity}, got {sale.quantity}"
                assert sale.total_amount == -(product.effective_store_price * quantity), f"Expected total_amount {-(product.effective_store_price * quantity)}, got {sale.total_amount}"
                print("Sale verification passed.")

                # Verify Financial Transaction
                fin_res = await session.execute(select(FinancialTransaction).where(FinancialTransaction.user_id == user_id).order_by(FinancialTransaction.id.desc()).limit(1))
                fin = fin_res.scalar_one()
                expected_amount = -(product.effective_store_price * quantity)
                assert fin.amount == expected_amount, f"Expected fin amount {expected_amount}, got {fin.amount}"
                assert fin.type == FinancialTransactionType.PAYMENT, f"Expected type PAYMENT, got {fin.type}"
                print("Financial Transaction verification passed.")

                print("All checks passed! The logic works flawlessly.")
            finally:
                # ROLLBACK everything so we don't pollute the production database
                await nested_txn.rollback()
                print("Transaction rolled back.")

if __name__ == "__main__":
    asyncio.run(test_customer_return())
