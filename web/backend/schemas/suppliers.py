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
    receivable_debt: Decimal = Decimal(0)
    payable_debt: Decimal = Decimal(0)
    net_balance: Decimal = Decimal(0)

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


class SupplierReturnLineItemOut(BaseModel):
    product_id: int
    sku: str
    quantity: int
    price_per_unit: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class SupplierReturnCreate(BaseModel):
    items: list[SupplierInvoiceLineItemIn] = Field(..., min_length=1)  # Reuse input item schema
    notes: str | None = None


class SupplierReturnOut(BaseModel):
    id: int
    supplier_id: int
    total_amount: Decimal
    notes: str | None
    created_at: datetime
    user_name: str | None = None
    items: list[SupplierReturnLineItemOut] = []

    model_config = {"from_attributes": True}


class SupplierReceiptLineItemOut(BaseModel):
    product_id: int
    sku: str
    quantity: int
    price_per_unit: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class SupplierReceiptCreate(BaseModel):
    items: list[SupplierInvoiceLineItemIn] = Field(..., min_length=1)
    notes: str | None = None


class SupplierReceiptOut(BaseModel):
    id: int
    supplier_id: int
    total_amount: Decimal
    notes: str | None
    created_at: datetime
    user_name: str | None = None
    items: list[SupplierReceiptLineItemOut] = []

    model_config = {"from_attributes": True}


class SupplierPayoutCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    notes: str | None = None


class SupplierPayoutOut(BaseModel):
    id: int
    supplier_id: int
    amount: Decimal
    notes: str | None
    created_at: datetime
    user_name: str | None = None

    model_config = {"from_attributes": True}


class SupplierOutgoingReturnLineItemOut(BaseModel):
    product_id: int
    sku: str
    quantity: int
    price_per_unit: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class SupplierOutgoingReturnCreate(BaseModel):
    items: list[SupplierInvoiceLineItemIn] = Field(..., min_length=1)
    notes: str | None = None


class SupplierOutgoingReturnOut(BaseModel):
    id: int
    supplier_id: int
    total_amount: Decimal
    notes: str | None
    created_at: datetime
    user_name: str | None = None
    items: list[SupplierOutgoingReturnLineItemOut] = []

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
    receivable_debt: Decimal
    payable_debt: Decimal
    net_balance: Decimal
    total_invoiced: Decimal
    total_paid: Decimal
    total_returned: Decimal
    total_received: Decimal
    total_payout: Decimal
    total_returned_to_partner: Decimal
    invoices: list[SupplierInvoiceOut]
    payments: list[SupplierPaymentOut]
    returns: list[SupplierReturnOut]
    receipts: list[SupplierReceiptOut]
    payouts: list[SupplierPayoutOut]
    outgoing_returns: list[SupplierOutgoingReturnOut]

    model_config = {"from_attributes": True}
