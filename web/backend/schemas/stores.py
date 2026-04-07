from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.enums import StoreType
from typing import Optional


class StoreOut(BaseModel):
    id: int
    name: str
    address: str
    store_type: StoreType
    current_debt: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


class StoreCatalogCard(BaseModel):
    id: int
    name: str
    address: str
    total_items: int
    total_value: Decimal


class StoreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field("", max_length=500)
    store_type: StoreType = StoreType.STORE


class InventoryItemOut(BaseModel):
    product_id: int
    product_sku: str
    quantity: int
    is_display: bool = False


class EmployeeCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=4, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., description="seller | warehouse")

class StoreUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[str] = Field(None, max_length=500)

class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, min_length=3, max_length=255)
    role: Optional[str] = Field(None, description="seller | warehouse")
    password: Optional[str] = Field(None, min_length=4, max_length=255)

class ReceiveStockInput(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, description="Quantity to receive")


class BulkReceiveItem(BaseModel):
    sku: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., gt=0)
    price: Optional[Decimal] = Field(None, description="New price of the product if applicable")


class BulkReceiveInput(BaseModel):
    items: list[BulkReceiveItem]


class DispatchDisplayInput(BaseModel):
    product_id: int
    target_store_id: int
    quantity: int = Field(..., gt=0)
