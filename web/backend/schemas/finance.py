from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CashCollectionRequest(BaseModel):
    store_id: int
    amount: Decimal = Field(gt=0, description="Amount to collect")


class CashCollectionHistoryItem(BaseModel):
    id: int
    store_id: int
    store_name: str
    user_id: int
    user_name: str
    amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class CashCollectionSummary(BaseModel):
    store_id: int
    store_name: str
    current_debt: Decimal

    class Config:
        from_attributes = True
