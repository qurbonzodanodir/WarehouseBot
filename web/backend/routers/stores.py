from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.models.enums import UserRole
from app.models.store import Store
from app.models.user import User
from app.services.store_service import StoreService
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.stores import EmployeeCreate, StoreCreate, StoreOut, StoreCatalogCard, StoreUpdate, EmployeeUpdate

router = APIRouter(prefix="/stores", tags=["Stores"])


@router.get(
    "",
    response_model=list[StoreOut],
    summary="Список магазинов",
)
async def list_stores(
    session: SessionDep,
    current_user: CurrentUser,
    include_inactive: bool = Query(False),
) -> list[StoreOut]:
    stmt = select(Store).order_by(Store.id)
    if not include_inactive:
        stmt = stmt.where(Store.is_active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/catalog",
    response_model=list[StoreCatalogCard],
    summary="Каталог магазинов (статистика)",
)
async def get_store_catalog(
    session: SessionDep,
    current_user: CurrentUser,
) -> list[StoreCatalogCard]:
    from sqlalchemy import func
    from app.models.inventory import Inventory
    from app.models.display_inventory import DisplayInventory
    from app.models.product import Product
    from decimal import Decimal

    # Subquery for regular inventory totals per store
    inv_sub = (
        select(
            Inventory.store_id,
            func.sum(Inventory.quantity).label("qty"),
            func.sum(Inventory.quantity * Product.price).label("val")
        )
        .join(Product, Inventory.product_id == Product.id)
        .group_by(Inventory.store_id)
        .subquery()
    )

    # Subquery for display inventory totals per store
    disp_sub = (
        select(
            DisplayInventory.store_id,
            func.sum(DisplayInventory.quantity).label("qty"),
            func.sum(DisplayInventory.quantity * Product.price).label("val")
        )
        .join(Product, DisplayInventory.product_id == Product.id)
        .group_by(DisplayInventory.store_id)
        .subquery()
    )

    stmt = (
        select(
            Store.id,
            Store.name,
            Store.address,
            (func.coalesce(inv_sub.c.qty, 0) + func.coalesce(disp_sub.c.qty, 0)).label("total_items"),
            (func.coalesce(inv_sub.c.val, Decimal("0")) + func.coalesce(disp_sub.c.val, Decimal("0"))).label("total_value")
        )
        .outerjoin(inv_sub, Store.id == inv_sub.c.store_id)
        .outerjoin(disp_sub, Store.id == disp_sub.c.store_id)
        .where(Store.is_active.is_(True))
        .order_by(Store.id)
    )

    if current_user.role == UserRole.SELLER:
        stmt = stmt.where(Store.id == current_user.store_id)

    result = await session.execute(stmt)
    rows = result.all()

    return [
        StoreCatalogCard(
            id=row.id,
            name=row.name,
            address=row.address,
            total_items=int(row.total_items),
            total_value=Decimal(row.total_value),
        )
        for row in rows
    ]


@router.get(
    "/{store_id}",
    response_model=StoreOut,
    summary="Детали магазина",
)
async def get_store(
    store_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> StoreOut:
    store = await session.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return store


@router.post(
    "",
    response_model=StoreOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать магазин (только Owner)",
)
async def create_store(
    body: StoreCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> StoreOut:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    store_svc = StoreService(session)
    store = await store_svc.create_store(name=body.name, address=body.address)
    await session.commit()
    await session.refresh(store)
    return store


@router.get(
    "/{store_id}/employees",
    summary="Сотрудники магазина",
)
async def get_store_employees(
    store_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[dict]:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    result = await session.execute(
        select(User).where(User.store_id == store_id, User.is_active.is_(True))
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "telegram_id": u.telegram_id,
            "email": u.email,
            "name": u.name,
            "role": u.role.value,
            "is_active": u.is_active,
        }
        for u in users
    ]

@router.put(
    "/{store_id}",
    response_model=StoreOut,
    summary="Обновить данные магазина (Owner only)",
)
async def update_store(
    store_id: int,
    body: StoreUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> StoreOut:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
    
    store = await session.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
        
    if body.name is not None:
        store.name = body.name
    if body.address is not None:
        store.address = body.address
        
    await session.commit()
    await session.refresh(store)
    return store

@router.put(
    "/employees/{employee_id}",
    summary="Обновить данные сотрудника (Owner only)",
)
async def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
    
    user = await session.get(User, employee_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        
    if body.name is not None:
        user.name = body.name
    if body.email is not None:
        user.email = body.email
    if body.role is not None:
        try:
            user.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    if body.password is not None and body.password.strip():
        from app.core.security import get_password_hash
        user.password_hash = get_password_hash(body.password)
        
    await session.commit()
    await session.refresh(user)
    
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "is_active": user.is_active,
    }


@router.post(
    "/{store_id}/employees",
    status_code=status.HTTP_201_CREATED,
    summary="Создать сотрудника (только Owner)",
    description="Создает нового сотрудника с email/паролем. Сотрудник может потом привязать Telegram через /login.",
)
async def create_employee(
    store_id: int,
    body: EmployeeCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    import bcrypt

    if current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    # Check store exists
    store = await session.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    # Check email uniqueness
    existing = await session.execute(
        select(User).where(User.email == body.email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email уже используется")

    # Validate role
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Неизвестная роль: {body.role}")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    user = User(
        email=body.email.lower(),
        password_hash=password_hash,
        name=body.name,
        role=role,
        store_id=store_id,
        is_active=True,
        language_code="ru",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "store_id": user.store_id,
        "is_active": user.is_active,
    }

