from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_seller_menu(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=_("btn_display")),
                KeyboardButton(text=_("btn_order")),
            ],
            [
                KeyboardButton(text=_("btn_sales_list")),
                KeyboardButton(text=_("btn_language")),
            ],
            [
                KeyboardButton(text=_("btn_more")),
            ],
        ],
        resize_keyboard=True,
    )


def get_seller_more_menu(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=_("btn_report")),
                KeyboardButton(text=_("btn_make_return")),
            ],
            [
                KeyboardButton(text="🔙 Назад"),
            ],
        ],
        resize_keyboard=True,
    )


def get_warehouse_menu(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=_("btn_wh_receive")),
                KeyboardButton(text=_("btn_wh_samples")),
            ],
            [
                KeyboardButton(text=_("btn_wh_requests")),
                KeyboardButton(text=_("btn_wh_stock")),
            ],
            [
                KeyboardButton(text=_("btn_language")),
                KeyboardButton(text=_("btn_more")),
            ],
        ],
        resize_keyboard=True,
    )


def get_warehouse_more_menu(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=_("btn_wh_shipments")),
                KeyboardButton(text=_("btn_wh_add_product")),
            ],
            [
                KeyboardButton(text=_("btn_back")),
            ],
        ],
        resize_keyboard=True,
    )


def get_owner_menu(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=_("btn_dashboard")),
                KeyboardButton(text=_("btn_collection")),
            ],
            [
                KeyboardButton(text=_("btn_catalog")),
                KeyboardButton(text=_("btn_restock")),
            ],
            [
                KeyboardButton(text=_("btn_management")),
                KeyboardButton(text=_("btn_language")),
            ],
        ],
        resize_keyboard=True,
    )


def get_owner_mgmt_menu(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=_("btn_stores")),
                KeyboardButton(text=_("btn_employees")),
            ],
            [
                KeyboardButton(text=_("btn_debtors")),
                KeyboardButton(text=_("btn_rating")),
            ],
            [
                KeyboardButton(text=_("btn_back")),
            ],
        ],
        resize_keyboard=True,
    )

