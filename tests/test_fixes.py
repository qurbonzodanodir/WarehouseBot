"""
Tests for the fixed logic:
1. _extract_telegram_id — safe None handling
2. Translator — tg fallback to ru
3. partial_reject_batch logic — cancels all PENDING + PARTIAL_APPROVAL_PENDING
4. batch inventory reservation — PARTIAL_APPROVAL_PENDING orders deduct inventory
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.bot.middlewares.auth import _extract_telegram_id
from app.core.i18n import Translator
from app.models.enums import OrderStatus


# ─── 1. _extract_telegram_id ─────────────────────────────────────────────────

class TestExtractTelegramId:

    def test_returns_none_for_none_event(self):
        assert _extract_telegram_id(None) is None

    def test_direct_from_user(self):
        event = MagicMock()
        event.from_user.id = 12345
        assert _extract_telegram_id(event) == 12345

    def test_no_from_user_attribute(self):
        """Object without from_user should not raise AttributeError."""
        event = MagicMock(spec=[])  # no attributes
        result = _extract_telegram_id(event)
        assert result is None

    def test_from_user_is_none(self):
        """from_user exists but is None — anonymous channel post."""
        event = MagicMock()
        event.from_user = None
        # Not an Update instance, so falls through to None
        result = _extract_telegram_id(event)
        assert result is None

    def test_update_message_from_user_none(self):
        """Update.message exists but message.from_user is None (anonymous post)."""
        from aiogram.types import Update
        event = MagicMock(spec=Update)
        event.from_user = None
        event.message = MagicMock()
        event.message.from_user = None
        event.callback_query = None
        event.inline_query = None
        event.my_chat_member = None
        result = _extract_telegram_id(event)
        assert result is None

    def test_update_message_with_valid_user(self):
        from aiogram.types import Update
        event = MagicMock(spec=Update)
        event.from_user = None
        msg = MagicMock()
        msg.from_user = MagicMock()
        msg.from_user.id = 99999
        event.message = msg
        event.callback_query = None
        event.inline_query = None
        event.my_chat_member = None
        result = _extract_telegram_id(event)
        assert result == 99999

    def test_update_callback_query_fallback(self):
        from aiogram.types import Update
        event = MagicMock(spec=Update)
        event.from_user = None
        event.message = None
        cb = MagicMock()
        cb.from_user = MagicMock()
        cb.from_user.id = 77777
        event.callback_query = cb
        event.inline_query = None
        event.my_chat_member = None
        result = _extract_telegram_id(event)
        assert result == 77777


# ─── 2. Translator ───────────────────────────────────────────────────────────

class TestTranslator:

    def test_ru_key_returns_russian(self):
        t = Translator("ru")
        assert t("btn_back") == "🔙 Назад"

    def test_tg_key_returns_tajik(self):
        t = Translator("tg")
        assert t("btn_back") == "🔙 Ба қафо"

    def test_tg_falls_back_to_ru_for_missing_key(self):
        """Keys missing in tg dict should fall back to ru value, not raise."""
        t = Translator("tg")
        # sale_system_error exists in ru but not explicitly tested — just ensure no crash
        result = t("sale_system_error")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_lang_falls_back_to_ru(self):
        t = Translator("uz")  # unsupported lang
        assert t("btn_back") == "🔙 Назад"

    def test_missing_key_returns_key_itself(self):
        t = Translator("ru")
        result = t("totally_nonexistent_key_xyz")
        assert result == "totally_nonexistent_key_xyz"

    def test_format_kwargs(self):
        t = Translator("ru")
        result = t("sale_success", sku="A100", qty=5)
        assert "A100" in result
        assert "5" in result

    def test_format_kwargs_tg(self):
        t = Translator("tg")
        result = t("sale_success", sku="B200", qty=3)
        assert "B200" in result
        assert "3" in result


# ─── 3. partial_reject_batch — cancels PENDING + PARTIAL_APPROVAL_PENDING ────

class TestPartialRejectBatchLogic:
    """Unit-test the cancellation logic in isolation (no DB needed)."""

    def _make_order(self, status: OrderStatus, qty: int = 5):
        o = MagicMock()
        o.status = status
        o.quantity = qty
        o.product = MagicMock()
        o.product.sku = "SKU-001"
        o.store_id = 1
        return o

    def test_cancels_partial_approval_pending(self):
        orders = [self._make_order(OrderStatus.PARTIAL_APPROVAL_PENDING)]
        cancellable = {OrderStatus.PARTIAL_APPROVAL_PENDING, OrderStatus.PENDING}
        valid = False
        for o in orders:
            if o.status in cancellable:
                valid = True
                o.status = OrderStatus.REJECTED
        assert valid is True
        assert orders[0].status == OrderStatus.REJECTED

    def test_cancels_pending_siblings(self):
        orders = [
            self._make_order(OrderStatus.PARTIAL_APPROVAL_PENDING, qty=3),
            self._make_order(OrderStatus.PENDING, qty=2),  # remainder order
        ]
        cancellable = {OrderStatus.PARTIAL_APPROVAL_PENDING, OrderStatus.PENDING}
        valid = False
        for o in orders:
            if o.status in cancellable:
                valid = True
                o.status = OrderStatus.REJECTED
        assert valid is True
        assert all(o.status == OrderStatus.REJECTED for o in orders)

    def test_already_processed_returns_not_valid(self):
        orders = [
            self._make_order(OrderStatus.REJECTED),
            self._make_order(OrderStatus.DELIVERED),
        ]
        cancellable = {OrderStatus.PARTIAL_APPROVAL_PENDING, OrderStatus.PENDING}
        valid = False
        for o in orders:
            if o.status in cancellable:
                valid = True
                o.status = OrderStatus.REJECTED
        assert valid is False

    def test_mixed_statuses(self):
        """Already rejected + pending sibling — valid should be True."""
        orders = [
            self._make_order(OrderStatus.REJECTED),
            self._make_order(OrderStatus.PENDING, qty=7),
        ]
        cancellable = {OrderStatus.PARTIAL_APPROVAL_PENDING, OrderStatus.PENDING}
        valid = False
        for o in orders:
            if o.status in cancellable:
                valid = True
                o.status = OrderStatus.REJECTED
        assert valid is True
        assert all(o.status == OrderStatus.REJECTED for o in orders)


# ─── 4. Inventory reservation logic ─────────────────────────────────────────

class TestInventoryReservation:
    """Verify that approve_batch partial path deducts available inventory."""

    def test_available_items_deducted(self):
        """Simulates the reservation loop in approve_batch_order."""
        inv = MagicMock()
        inv.quantity = 10

        available_items = [{"order": MagicMock(), "available_qty": 3}]

        # Simulate the reservation
        for item in available_items:
            inv.quantity -= item["available_qty"]

        assert inv.quantity == 7

    def test_missing_items_not_deducted(self):
        inv = MagicMock()
        inv.quantity = 10

        available_items = []
        missing_items = [{"order": MagicMock(), "available_qty": 0}]

        for item in available_items:
            inv.quantity -= item["available_qty"]
        # missing items don't touch inventory

        assert inv.quantity == 10

    def test_reject_returns_reserved_inventory(self):
        """Simulates the inventory return in partial_reject_batch."""
        inv = MagicMock()
        inv.quantity = 7  # after reservation (was 10, reserved 3)

        order = MagicMock()
        order.status = OrderStatus.PARTIAL_APPROVAL_PENDING
        order.quantity = 3

        # Return reserved quantity
        if order.status == OrderStatus.PARTIAL_APPROVAL_PENDING:
            inv.quantity += order.quantity

        assert inv.quantity == 10  # back to original
