from decimal import Decimal
from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    id: int
    sku: str
    price: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    price: Decimal = Field(..., gt=0)


class ProductUpdate(BaseModel):
    price: Decimal | None = Field(None, gt=0)
    is_active: bool | None = None


class ProductInventoryOut(BaseModel):
    store_id: int
    store_name: str
    quantity: int
    is_display: bool = False


class ProductPaginationOut(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
    total_pages: int
