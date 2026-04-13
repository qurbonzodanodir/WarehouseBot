import enum
from sqlalchemy import Enum as SA_Enum

def db_enum(enum_cls, name: str):
    """
    Returns a SQLAlchemy Enum type configured to use member values for storage.
    native_enum=False stores as VARCHAR but validates against the Enum values.
    """
    return SA_Enum(
        enum_cls,
        name=name,
        values_callable=lambda obj: [e.value for e in obj],
        native_enum=False
    )

class CaseInsensitiveEnum(str, enum.Enum):
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return super()._missing_(value)
    
    def __str__(self):
        return self.value.lower()

class StoreType(CaseInsensitiveEnum):
    WAREHOUSE = "warehouse"
    STORE = "store"

class UserRole(CaseInsensitiveEnum):
    SELLER = "seller"
    WAREHOUSE = "warehouse"
    ADMIN = "admin"
    OWNER = "owner"

class OrderStatus(CaseInsensitiveEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    SOLD = "sold"
    RETURNED = "returned"
    RETURN_PENDING = "return_pending"
    DISPLAY_DISPATCHED = "display_dispatched"
    DISPLAY_DELIVERED = "display_delivered"
    DISPLAY_REJECTED = "display_rejected"
    DISPLAY_RETURN_PENDING = "display_return_pending"
    DISPLAY_RETURNED = "display_returned"
    PARTIAL_APPROVAL_PENDING = "partial_approval_pending"

class StockMovementType(CaseInsensitiveEnum):
    RECEIVE_FROM_SUPPLIER = "receive_from_supplier"
    DISPATCH_TO_STORE = "dispatch_to_store"
    RETURN_TO_WAREHOUSE = "return_to_warehouse"
    SALE = "sale"
    DISPLAY_DISPATCH = "display_dispatch"
    DISPLAY_RECEIVE = "display_receive"
    DISPLAY_RETURN = "display_return"
    DISPATCH_TO_WHOLESALER = "dispatch_to_wholesaler"

class FinancialTransactionType(CaseInsensitiveEnum):
    PAYMENT = "payment"
    COLLECTION = "collection"

class DebtLedgerReason(CaseInsensitiveEnum):
    SALE_COMPLETED = "sale_completed"
    CASH_COLLECTION = "cash_collection"
    RETURN_APPROVED = "return_approved"
