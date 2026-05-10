"""
SettingsService — manages system-wide settings stored in `system_settings` table.

Implements a simple in-process cache so reads are O(1) after first hit.
Cache is invalidated on update.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting


# Known setting keys
KEY_RETAIL_MARKUP = "retail_markup"

# Defaults applied if a setting row is missing entirely
_DEFAULTS: dict[str, str] = {
    KEY_RETAIL_MARKUP: "1.0",
}


class SettingsService:
    """Read/write system settings with in-memory caching."""

    # Class-level cache shared across instances (process-wide)
    _cache: dict[str, str] = {}
    _loaded: bool = False

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------------------------------------------------------------------
    # Cache
    # ---------------------------------------------------------------------
    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cache = {}
        cls._loaded = False

    async def _ensure_loaded(self) -> None:
        if SettingsService._loaded:
            return
        result = await self.session.execute(select(SystemSetting))
        rows = result.scalars().all()
        SettingsService._cache = {row.key: row.value for row in rows}
        SettingsService._loaded = True

    # ---------------------------------------------------------------------
    # Generic getters
    # ---------------------------------------------------------------------
    async def get(self, key: str, default: str | None = None) -> str:
        await self._ensure_loaded()
        if key in SettingsService._cache:
            return SettingsService._cache[key]
        if default is not None:
            return default
        return _DEFAULTS.get(key, "")

    async def get_decimal(self, key: str, default: Decimal = Decimal("0")) -> Decimal:
        raw = await self.get(key, str(default))
        try:
            return Decimal(raw)
        except (InvalidOperation, TypeError):
            return default

    async def set(self, key: str, value: str) -> None:
        existing = await self.session.get(SystemSetting, key)
        if existing is None:
            self.session.add(SystemSetting(key=key, value=value))
        else:
            existing.value = value
        await self.session.flush()
        # Update cache immediately so subsequent reads in same txn are correct
        SettingsService._cache[key] = value

    async def set_many(self, items: dict[str, Any]) -> None:
        for key, value in items.items():
            await self.set(key, str(value))

    async def all(self) -> dict[str, str]:
        await self._ensure_loaded()
        # Merge with defaults for missing keys
        merged = dict(_DEFAULTS)
        merged.update(SettingsService._cache)
        return merged

    # ---------------------------------------------------------------------
    # Typed convenience accessors
    # ---------------------------------------------------------------------
    async def get_retail_markup(self) -> Decimal:
        return await self.get_decimal(KEY_RETAIL_MARKUP, Decimal("1.0"))

    async def retail_price(self, cost_price: Decimal) -> Decimal:
        markup = await self.get_retail_markup()
        return cost_price + markup
