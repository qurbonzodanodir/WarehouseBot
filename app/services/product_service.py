from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import Inventory
from app.models.product import Product


def _clean_col(col):
    """Remove spaces and dashes, lowercase a DB column for comparison."""
    return func.replace(func.replace(func.lower(col), ' ', ''), '-', '')


async def search_catalog(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 10,
) -> tuple[Product | None, list[Product]]:
    """
    Search the product catalog.

    Returns (exact_match, partial_matches).
    - If an exact SKU match is found: (product, [])
    - If partial matches found: (None, [product, ...])
    - If nothing found: (None, [])
    """
    clean_query = query.strip().lower().replace(" ", "").replace("-", "")
    clean_sku = _clean_col(Product.sku)
    clean_name = _clean_col(Product.name)

    # 1) Exact SKU match
    result = await session.execute(
        select(Product).where(
            Product.is_active.is_(True),
            clean_sku == clean_query,
        )
    )
    product = result.scalar_one_or_none()
    if product:
        return product, []

    # 2) Partial match by SKU or name
    result = await session.execute(
        select(Product).where(
            Product.is_active.is_(True),
            (clean_sku.ilike(f"%{clean_query}%")) |
            (clean_name.ilike(f"%{clean_query}%")),
        ).limit(limit)
    )
    products = list(result.scalars().all())
    return None, products


async def search_store_inventory(
    session: AsyncSession,
    query: str,
    store_id: int,
    *,
    require_stock: bool = False,
    limit: int = 10,
) -> tuple[Product | None, list[Product], Inventory | None]:
    """
    Search a store's inventory by product SKU/name.

    Args:
        store_id: The store whose inventory to search.
        require_stock: If True, only return items with quantity > 0.

    Returns (exact_match, partial_matches, inventory_record).
    - If exact match: (product, [], inventory)
    - If partial matches: (None, [products...], None)
    - If nothing: (None, [], None)
    """
    clean_query = query.strip().lower().replace(" ", "").replace("-", "")
    clean_sku = _clean_col(Product.sku)
    clean_name = _clean_col(Product.name)

    base_filters = [
        Inventory.store_id == store_id,
        Product.is_active.is_(True),
    ]
    if require_stock:
        base_filters.append(Inventory.quantity > 0)

    # 1) Exact SKU match
    result = await session.execute(
        select(Inventory)
        .options(selectinload(Inventory.product))
        .join(Product)
        .where(*base_filters, clean_sku == clean_query)
    )
    inv = result.scalar_one_or_none()
    if inv:
        return inv.product, [], inv

    # 2) Partial match
    result = await session.execute(
        select(Inventory)
        .options(selectinload(Inventory.product))
        .join(Product)
        .where(
            *base_filters,
            (clean_sku.ilike(f"%{clean_query}%")) |
            (clean_name.ilike(f"%{clean_query}%")),
        ).limit(limit)
    )
    inventories = list(result.scalars().all())
    products = [inv.product for inv in inventories]
    return None, products, None
