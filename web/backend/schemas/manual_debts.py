from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ManualDebtTransactionType


class ManualDebtCreate(BaseModel):
    store_id: int
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    operation_date: date = Field(default_factory=date.today)
    comment: str | None = Field(default=None, max_length=1000)


class ManualDebtUpdate(BaseModel):
    amount: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    operation_date: date | None = None
    comment: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("Укажите данные для изменения")
        return self


class ManualDebtTransactionOut(BaseModel):
    id: int
    store_id: int
    store_name: str
    user_id: int
    user_name: str
    type: ManualDebtTransactionType
    amount: Decimal
    operation_date: date
    comment: str | None
    created_at: datetime


class ManualDebtStoreSummary(BaseModel):
    store_id: int
    store_name: str
    balance: Decimal
    last_transaction: ManualDebtTransactionOut | None


class ManualDebtOverview(BaseModel):
    stores: list[ManualDebtStoreSummary]
    stores_with_debt: int
    total_debt: Decimal
    charged_this_month: Decimal


class ManualDebtStoreDetail(BaseModel):
    store_id: int
    store_name: str
    balance: Decimal
    transactions: list[ManualDebtTransactionOut]
