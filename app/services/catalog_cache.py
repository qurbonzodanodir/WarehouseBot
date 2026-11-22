"""
Lightweight in-memory TTL cache for catalog browsing data.

Cached: product lists for pagination (names, SKUs, brands, quantities).
NOT cached: individual stock checks, cart operations, transactions.

TTL = 60 seconds — changes in product catalog appear within a minute.
No external dependencies (no Redis, no cachetools).
Single-threaded asyncio — no locking needed.
"""

import time
from typing import Any

_cache: dict[str, tuple[float, Any]] = {}
_TTL = 60  # seconds


def get_cached(key: str) -> Any | None:
    """Return cached value if present and not expired, else None."""
    entry = _cache.get(key)
    if entry is None:
        return None
    cached_at, value = entry
    if time.monotonic() - cached_at > _TTL:
        del _cache[key]
        return None
    return value


def set_cached(key: str, value: Any) -> None:
    """Store a value with the current timestamp."""
    _cache[key] = (time.monotonic(), value)


def invalidate_store(store_id: int) -> None:
    """Remove all cached entries for a specific store."""
    prefix = f"store:{store_id}:"
    for k in [k for k in _cache if k.startswith(prefix)]:
        del _cache[k]


def invalidate_all() -> None:
    """Clear the entire cache."""
    _cache.clear()
