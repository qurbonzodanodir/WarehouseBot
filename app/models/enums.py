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


class TransactionType(str, enum.Enum):
    SALE = "sale"
    RETURN = "return"
    CASH_COLLECTION = "cash_collection"
