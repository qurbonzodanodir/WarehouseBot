from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.store import Store
from app.models.financial_transaction import FinancialTransaction
from app.models.enums import FinancialTransactionType

class AnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_store_rating(self, start_date: datetime, end_date: datetime = None) -> list:
        """
        Returns a list of tuples (store_name, total_revenue) ranked by revenue.
        """
        stmt = (
            select(
                Store.name,
                func.coalesce(func.sum(FinancialTransaction.amount), 0).label("total"),
            )
            .join(FinancialTransaction, FinancialTransaction.store_id == Store.id, isouter=True)
            .where(
                Store.is_active.is_(True),
                FinancialTransaction.type == FinancialTransactionType.PAYMENT,
                FinancialTransaction.created_at >= start_date,
            )
        )
        
        if end_date:
            stmt = stmt.where(FinancialTransaction.created_at <= end_date)
            
        stmt = (
            stmt.group_by(Store.id, Store.name)
            .order_by(func.sum(FinancialTransaction.amount).desc())
        )
        
        result = await self.session.execute(stmt)
        return result.all()
