from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_seller_menu(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=_("btn_sale")),
                KeyboardButton(text=_("btn_order")),
            ],
            [
                KeyboardButton(text=_("btn_vitrine")),
                KeyboardButton(text=_("btn_sales_list")),
            ],
            [
                KeyboardButton(text=_("btn_more")),
                KeyboardButton(text=_("btn_language")),
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
                KeyboardButton(text=_("btn_back")),
            ],
        ],
        resize_keyboard=True,
    )


def get_warehouse_menu(_) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=_("btn_wh_requests")),
            ],
            [
                KeyboardButton(text=_("btn_wh_stock")),
                KeyboardButton(text=_("btn_language")),
            ],
        ],
        resize_keyboard=True,
    )





