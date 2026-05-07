from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel
from app.models.enums import OrderStatus


class ProductBrief(BaseModel):
    id: int
    sku: str
    price: Decimal

    model_config = {"from_attributes": True}


class StoreBrief(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    batch_id: str | None
    store_id: int
    store: StoreBrief
    product_id: int
    product: ProductBrief
    quantity: int
    price_per_item: Decimal
    total_price: Decimal
    status: OrderStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    store_id: int
    product_id: int
    quantity: int
    batch_id: str | None = None


class WarehouseDispatchItem(BaseModel):
    product_id: int
    quantity: int


class WarehouseDispatchCreate(BaseModel):
    store_id: int
    items: list[WarehouseDispatchItem]


class OrderFilters(BaseModel):
    store_id: int | None = None
    status: OrderStatus | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = 50
    offset: int = 0
