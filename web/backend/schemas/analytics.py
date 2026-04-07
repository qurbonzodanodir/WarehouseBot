from decimal import Decimal
from pydantic import BaseModel


class StoreDebt(BaseModel):
    store_id: int
    store_name: str
    current_debt: Decimal


class StoreRevenue(BaseModel):
    store_name: str
    total_revenue: Decimal


class OrderStatusCount(BaseModel):
    status: str
    count: int


class DashboardResponse(BaseModel):
    total_orders_today: int
    total_revenue_today: Decimal
    total_debt: Decimal
    pending_orders: int
    store_debts: list[StoreDebt]
    store_revenues: list[StoreRevenue]
    orders_by_status: list[OrderStatusCount]
