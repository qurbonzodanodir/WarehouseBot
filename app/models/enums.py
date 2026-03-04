import enum


class UserRole(str, enum.Enum):
    SELLER = "seller"
    WAREHOUSE = "warehouse"
    ADMIN = "admin"
    OWNER = "owner"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    SOLD = "sold"
    RETURNED = "returned"
    RETURN_PENDING = "return_pending"
    # Display transfers
    DISPLAY_DISPATCHED = "display_dispatched"
    DISPLAY_DELIVERED = "display_delivered"
    DISPLAY_REJECTED = "display_rejected"


class TransactionType(str, enum.Enum):
    SALE = "sale"
    RETURN = "return"
    CASH_COLLECTION = "cash_collection"
    DISPLAY_TRANSFER = "display_transfer"
    STOCK_RECEIVE = "stock_receive"
