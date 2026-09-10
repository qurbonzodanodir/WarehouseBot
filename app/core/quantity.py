"""Shared quantity moderation for seller / return / order flows."""

from __future__ import annotations

from decimal import Decimal

# Hard cap for one transaction line. Blocks SKU pasted as quantity (6+ digits).
MAX_TRANSACTION_QUANTITY = 500

# Hard cap for money impact of one sale/return line.
MAX_TRANSACTION_AMOUNT = Decimal("200000")


def parse_positive_int(raw: str | None) -> int | None:
    """Return a positive int from user text, or None if invalid."""
    if raw is None:
        return None
    text = raw.strip()
    if not text.isdigit():
        return None
    value = int(text)
    if value <= 0:
        return None
    return value


def validate_transaction_quantity(
    quantity: int,
    *,
    max_qty: int = MAX_TRANSACTION_QUANTITY,
) -> None:
    """Raise ValueError if quantity is not allowed."""
    if quantity <= 0:
        raise ValueError("Количество должно быть больше 0.")
    if quantity > max_qty:
        raise ValueError(
            f"Слишком большое количество: максимум {max_qty} шт. за одну операцию."
        )


def validate_transaction_amount(
    quantity: int,
    price_per_item: Decimal | float | int,
    *,
    max_amount: Decimal = MAX_TRANSACTION_AMOUNT,
) -> None:
    """Raise ValueError if |qty * price| exceeds the money cap."""
    amount = abs(Decimal(str(price_per_item)) * Decimal(quantity))
    if amount > max_amount:
        raise ValueError(
            f"Слишком большая сумма операции: максимум {max_amount:.0f} TJS."
        )
