from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    """Seller ordering a product from warehouse."""
    select_product = State()   # choosing product from catalog
    enter_quantity = State()   # entering how many to order
    cart_action = State()      # reviewing cart and choosing next action


class SaleFlow(StatesGroup):
    """Seller recording a sale."""
    select_product = State()   # choosing product from inventory
    enter_quantity = State()   # entering how many sold


class ReturnFlow(StatesGroup):
    """Seller recording a return."""
    select_product = State()
    enter_quantity = State()





class RegistrationFlow(StatesGroup):
    enter_code = State()







class ReceiveStockFlow(StatesGroup):
    """Warehouse worker receiving new stock."""
    select_product = State()
    enter_quantity = State()


class DisplayTransferFlow(StatesGroup):
    """Warehouse worker sending display samples to a store."""
    select_store = State()
    select_product = State()
    enter_quantity = State()




