from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    """Seller ordering a product from warehouse."""
    select_product = State()   # choosing product from catalog
    enter_quantity = State()   # entering how many to order


class SaleFlow(StatesGroup):
    """Seller recording a sale."""
    select_product = State()   # choosing product from inventory
    enter_quantity = State()   # entering how many sold


class ReturnFlow(StatesGroup):
    """Seller recording a return."""
    select_product = State()
    enter_quantity = State()
    enter_reason = State()     # mandatory reason


class CashCollectionFlow(StatesGroup):
    select_store = State()     # picking which store
    enter_amount = State()     # entering custom amount


class AddProductFlow(StatesGroup):
    enter_sku = State()
    enter_name = State()
    enter_price = State()


class AddStockFlow(StatesGroup):
    select_store = State()
    select_product = State()
    enter_quantity = State()


class RegistrationFlow(StatesGroup):
    enter_code = State()


class AddStoreFlow(StatesGroup):
    enter_name = State()
    enter_address = State()


class InviteFlow(StatesGroup):
    select_store = State()
    select_role = State()


class ReceiveStockFlow(StatesGroup):
    """Warehouse worker receiving new stock."""
    select_product = State()
    enter_quantity = State()
    # Inline product creation
    new_product_sku = State()
    new_product_name = State()
    new_product_price = State()


class DisplayTransferFlow(StatesGroup):
    """Warehouse worker sending display samples to a store."""
    select_store = State()
    select_product = State()
    enter_quantity = State()
