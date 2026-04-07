from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.models.product import Product
from app.models.enums import UserRole
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.products import ProductCreate, ProductOut, ProductUpdate, ProductInventoryOut, ProductPaginationOut

router = APIRouter(prefix="/products", tags=["Products"])


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
    page_size: int = Query(20, ge=1, le=100),
) -> ProductPaginationOut:
    stmt = select(Product).order_by(Product.sku)

    if only_inactive:
        stmt = stmt.where(Product.is_active.is_(False))
    elif not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))

    if search:
        pattern = f"%{search.lower()}%"
        from sqlalchemy import func
        stmt = stmt.where(func.lower(Product.sku).like(pattern))

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
    "/{product_id}",
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
    "/{product_id}/inventory",
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
    
    out = []
    for row in res_reg.all():
        out.append(ProductInventoryOut(
            store_id=row.id, 
            store_name=row.name, 
            quantity=int(row.quantity), 
            is_display=False
        ))
    for row in res_disp.all():
        out.append(ProductInventoryOut(
            store_id=row.id, 
            store_name=row.name, 
            quantity=int(row.quantity), 
            is_display=True
        ))
    
    return sorted(out, key=lambda x: x.quantity, reverse=True)


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

    try:
        product = Product(
            sku=body.sku,
            price=body.price,
            is_active=True,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Product with this SKU already exists")
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch(
    "/{product_id}",
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
    if body.is_active is not None:
        product.is_active = body.is_active

    await session.commit()
    await session.refresh(product)
    return product

@router.delete(
    "/{product_id}",
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cant_delete_used"
        )
