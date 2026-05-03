from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select

from app.models.brand import Brand
from app.models.product import Product
from app.models.enums import UserRole
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.brands import BrandCreate, BrandOut, BrandUpdate
from web.backend.schemas.products import (
    BrandStatOut,
    ProductCreate,
    ProductInventoryOut,
    ProductOut,
    ProductPaginationOut,
    ProductPickerOut,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.post(
    "/brands",
    response_model=BrandOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать фирму",
)
async def create_brand(
    body: BrandCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> BrandOut:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    name = body.name.strip()
    existing = await session.execute(select(Brand).where(Brand.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Brand already exists")

    brand = Brand(name=name)
    session.add(brand)
    await session.commit()
    await session.refresh(brand)
    return brand


@router.get(
    "/brands",
    response_model=list[BrandOut],
    summary="Справочник фирм",
)
async def list_brands(
    session: SessionDep,
    current_user: CurrentUser,
) -> list[BrandOut]:
    result = await session.execute(select(Brand).order_by(Brand.name))
    return list(result.scalars().all())


@router.get(
    "/brands/stats",
    response_model=list[BrandStatOut],
    summary="Статистика по фирмам",
)
async def list_brand_stats(
    session: SessionDep,
    current_user: CurrentUser,
) -> list[BrandStatOut]:
    result = await session.execute(
        select(
            Brand.id,
            Brand.name,
            select(func.count(Product.id))
            .where(Product.brand == Brand.name)
            .scalar_subquery()
            .label("product_count"),
        )
        .order_by(Brand.name)
    )
    return [
        BrandStatOut(
            id=row.id,
            name=row.name,
            product_count=int(row.product_count or 0),
        )
        for row in result.all()
    ]


@router.patch(
    "/brands/{brand_id}",
    response_model=BrandOut,
    summary="Переименовать фирму",
)
async def update_brand(
    brand_id: int,
    body: BrandUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> BrandOut:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    brand = await session.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    new_name = body.name.strip()
    existing = await session.execute(select(Brand).where(Brand.name == new_name, Brand.id != brand_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Brand already exists")

    old_name = brand.name
    brand.name = new_name
    products = await session.execute(select(Product).where(Product.brand == old_name))
    for product in products.scalars().all():
        product.brand = new_name

    await session.commit()
    await session.refresh(brand)
    return brand


@router.delete(
    "/brands/{brand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить фирму",
)
async def delete_brand(
    brand_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    brand = await session.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    in_use = await session.execute(select(Product.id).where(Product.brand == brand.name).limit(1))
    if in_use.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Brand is used by products")

    await session.delete(brand)
    await session.commit()


@router.get(
    "",
    response_model=ProductPaginationOut,
    summary="Каталог товаров",
)
async def list_products(
    session: SessionDep,
    current_user: CurrentUser,
    include_inactive: bool = Query(False),
    only_inactive: bool = Query(False),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=10000),
) -> ProductPaginationOut:
    stmt = select(Product).order_by(Product.id.desc())

    if only_inactive:
        stmt = stmt.where(Product.is_active.is_(False))
    elif not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))

    if search:
        pattern = f"%{search.lower()}%"
        from sqlalchemy import func
        stmt = stmt.where(
            func.lower(Product.sku).like(pattern) | func.lower(Product.brand).like(pattern)
        )

    # Total count for pagination
    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await session.execute(count_stmt)
    total = total_res.scalar() or 0

    # Apply pagination
    stmt = stmt.limit(page_size).offset((page - 1) * page_size)
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    import math
    return ProductPaginationOut(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0
    )


@router.get(
    "/options",
    response_model=list[ProductPickerOut],
    summary="Короткий список товаров для выбора",
)
async def list_product_options(
    session: SessionDep,
    current_user: CurrentUser,
    search: str | None = Query(None),
    product_ids: str | None = Query(None),
    include_inactive: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
) -> list[ProductPickerOut]:
    stmt = select(Product)

    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))

    if product_ids:
        parsed_ids = [
            int(raw_id)
            for raw_id in product_ids.split(",")
            if raw_id.strip().isdigit()
        ]
        if parsed_ids:
            stmt = stmt.where(Product.id.in_(parsed_ids))
        else:
            return []

    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(Product.sku).like(pattern) | func.lower(Product.brand).like(pattern)
        )

    stmt = stmt.order_by(Product.id.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/{product_id:int}",
    response_model=ProductOut,
    summary="Детали товара",
)
async def get_product(
    product_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProductOut:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.get(
    "/{product_id:int}/inventory",
    response_model=list[ProductInventoryOut],
    summary="Остатки товара по магазинам",
)
async def get_product_inventory(
    product_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[ProductInventoryOut]:
    from sqlalchemy import func
    from app.models.inventory import Inventory
    from app.models.display_inventory import DisplayInventory
    from app.models.store import Store

    # 1. Fetch regular inventory
    stmt_reg = (
        select(Store.id, Store.name, func.coalesce(Inventory.quantity, 0).label("quantity"))
        .join(Inventory, Store.id == Inventory.store_id)
        .where(Inventory.product_id == product_id)
        .where(Inventory.quantity > 0)
    )
    
    # 2. Fetch display inventory
    stmt_disp = (
        select(Store.id, Store.name, func.coalesce(DisplayInventory.quantity, 0).label("quantity"))
        .join(DisplayInventory, Store.id == DisplayInventory.store_id)
        .where(DisplayInventory.product_id == product_id)
        .where(DisplayInventory.quantity > 0)
    )

    if current_user.role == UserRole.SELLER:
        stmt_reg = stmt_reg.where(Store.id == current_user.store_id)
        stmt_disp = stmt_disp.where(Store.id == current_user.store_id)

    res_reg = await session.execute(stmt_reg)
    res_disp = await session.execute(stmt_disp)
    
    # Merge regular and display quantities by store so each store appears once.
    merged: dict[int, ProductInventoryOut] = {}

    for row in res_reg.all():
        merged[row.id] = ProductInventoryOut(
            store_id=row.id,
            store_name=row.name,
            quantity=int(row.quantity),
            is_display=False,
        )

    for row in res_disp.all():
        qty = int(row.quantity)
        if row.id in merged:
            merged[row.id].quantity += qty
            # Keep a single row per store; combined stock is represented as regular.
            merged[row.id].is_display = False
        else:
            merged[row.id] = ProductInventoryOut(
                store_id=row.id,
                store_name=row.name,
                quantity=qty,
                is_display=False,
            )
    
    return sorted(merged.values(), key=lambda x: x.quantity, reverse=True)


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить товар (только Owner)",
)
async def create_product(
    body: ProductCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProductOut:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    brand_exists = await session.execute(select(Brand).where(Brand.name == body.brand.strip()))
    if not brand_exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Brand not found")

    existing_res = await session.execute(select(Product).where(Product.sku == body.sku))
    existing_product = existing_res.scalar_one_or_none()

    if existing_product:
        if existing_product.is_active:
            raise HTTPException(status_code=400, detail="Product with this SKU already exists")
        else:
            existing_product.is_active = True
            existing_product.brand = body.brand.strip()
            existing_product.price = body.price
            session.add(existing_product)
            await session.commit()
            await session.refresh(existing_product)
            return existing_product

    product = Product(
        sku=body.sku,
        brand=body.brand.strip(),
        price=body.price,
        is_active=True,
    )
    session.add(product)
    try:
        await session.commit()
        await session.refresh(product)
        return product
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Product with this SKU already exists")


@router.patch(
    "/{product_id:int}",
    response_model=ProductOut,
    summary="Обновить товар (только Owner)",
)
async def update_product(
    product_id: int,
    body: ProductUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ProductOut:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    if body.price is not None:
        product.price = body.price
    if body.brand is not None:
        cleaned_brand = body.brand.strip()
        if cleaned_brand:
            brand_exists = await session.execute(select(Brand).where(Brand.name == cleaned_brand))
            if not brand_exists.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Brand not found")
            product.brand = cleaned_brand
    if body.is_active is not None:
        product.is_active = body.is_active

    await session.commit()
    await session.refresh(product)
    return product

@router.delete(
    "/{product_id:int}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить товар (только Owner)",
)
async def delete_product(
    product_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    try:
        await session.delete(product)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        product.is_active = False
        session.add(product)
        await session.commit()
