from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact_info: str | None = None
    address: str | None = None
    notes: str | None = None


class SupplierOut(BaseModel):
    id: int
    name: str
    contact_info: str | None
    address: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    current_debt: Decimal = Decimal(0)

    model_config = {"from_attributes": True}


class SupplierInvoiceLineItemIn(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)


class SupplierInvoiceLineItemOut(BaseModel):
    product_id: int
    sku: str
    quantity: int
    price_per_unit: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class SupplierInvoiceCreate(BaseModel):
    items: list[SupplierInvoiceLineItemIn] = Field(..., min_length=1)
    notes: str | None = None


class SupplierInvoiceOut(BaseModel):
    id: int
    supplier_id: int
    total_amount: Decimal
    notes: str | None
    created_at: datetime
    user_name: str | None = None
    items: list[SupplierInvoiceLineItemOut] = []

    model_config = {"from_attributes": True}


class SupplierPaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    notes: str | None = None


class SupplierPaymentOut(BaseModel):
    id: int
    supplier_id: int
    amount: Decimal
    notes: str | None
    created_at: datetime
    user_name: str | None = None

    model_config = {"from_attributes": True}


class SupplierDetailOut(BaseModel):
    id: int
    name: str
    contact_info: str | None
    address: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    current_debt: Decimal
    total_invoiced: Decimal
    total_paid: Decimal
    invoices: list[SupplierInvoiceOut]
    payments: list[SupplierPaymentOut]

    model_config = {"from_attributes": True}
