from app.models.enums import StoreType
from app.services.product_service import ProductService
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query, File, UploadFile, Form
import csv
import io
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.display_inventory import DisplayInventory
from app.models.inventory import Inventory
from app.models.enums import UserRole
from app.models.store import Store
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.stores import InventoryItemOut, ReceiveStockInput, BulkReceiveInput, DispatchDisplayInput, BulkVitrinaInput, PaginatedInventoryResponse
from app.bot.bot import bot
from app.services.notification_service import NotificationService
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get(
    "/{store_id:int}",
    response_model=PaginatedInventoryResponse,
    summary="Остатки магазина / склада",
    description="Возвращает товары с количеством для указанного магазина (включая витрину).",
)
async def get_store_inventory(
    store_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    include_empty: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> PaginatedInventoryResponse:
    if current_user.role == UserRole.SELLER and current_user.store_id != store_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # 1. Fetch regular inventory
    stmt_reg = (
        select(Inventory)
        .options(joinedload(Inventory.product))
        .where(Inventory.store_id == store_id)
    )
    if not include_empty:
        stmt_reg = stmt_reg.where(Inventory.quantity > 0)
    
    res_reg = await session.execute(stmt_reg)
    items_reg = res_reg.scalars().all()

    # 2. Fetch display inventory
    stmt_disp = (
        select(DisplayInventory)
        .options(joinedload(DisplayInventory.product))
        .where(DisplayInventory.store_id == store_id)
    )
    if not include_empty:
        stmt_disp = stmt_disp.where(DisplayInventory.quantity > 0)
    
    res_disp = await session.execute(stmt_disp)
    items_disp = res_disp.scalars().all()

    # Combine and merge by product_id
    merged = {}
    for inv in items_reg:
        product_id = inv.product_id
        if product_id in merged:
            merged[product_id].quantity += inv.quantity
        else:
            merged[product_id] = InventoryItemOut(
                product_id=inv.product_id,
                product_sku=inv.product.sku,
                quantity=inv.quantity,
                is_display=False
            )
    
    for inv in items_disp:
        product_id = inv.product_id
        if product_id in merged:
            merged[product_id].quantity += inv.quantity
            merged[product_id].is_display = True
        else:
            merged[product_id] = InventoryItemOut(
                product_id=inv.product_id,
                product_sku=inv.product.sku,
                quantity=inv.quantity,
                is_display=True
            )

    # Convert to list and sort by SKU
    items_list = list(merged.values())
    items_list.sort(key=lambda x: x.product_sku)

    # Apply pagination
    total = len(items_list)
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    paginated_items = items_list[offset:offset + page_size]

    return PaginatedInventoryResponse(
        items=paginated_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get(
    "",
    response_model=dict,
    summary="Остатки всех магазинов",
    description="Возвращает остатки сгруппированные по магазинам (только Owner/Warehouse, включая витрину).",
)
async def get_all_inventory(
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    if current_user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(status_code=403, detail="Access denied")

    stores_result = await session.execute(select(Store).where(Store.is_active.is_(True)))
    stores = stores_result.scalars().all()
    store_map = {store.id: store.name for store in stores}
    result = {store.id: {"store_name": store.name, "items": []} for store in stores}

    # Regular inventory for all stores in one query.
    reg_result = await session.execute(
        select(Inventory)
        .options(joinedload(Inventory.product))
        .where(Inventory.quantity > 0, Inventory.store_id.in_(store_map.keys()))
    )
    for inv in reg_result.scalars().all():
        result[inv.store_id]["items"].append(
            {
                "product_id": inv.product_id,
                "sku": inv.product.sku,
                "quantity": inv.quantity,
                "is_display": False,
            }
        )

    # Display inventory for all stores in one query.
    disp_result = await session.execute(
        select(DisplayInventory)
        .options(joinedload(DisplayInventory.product))
        .where(DisplayInventory.quantity > 0, DisplayInventory.store_id.in_(store_map.keys()))
    )
    for inv in disp_result.scalars().all():
        result[inv.store_id]["items"].append(
            {
                "product_id": inv.product_id,
                "sku": inv.product.sku,
                "quantity": inv.quantity,
                "is_display": True,
            }
        )

    return result

@router.post(
    "/receive",
    response_model=dict,
    summary="Приход товара на Главный Склад",
    description="Добавляет количество существующего товара на Главный Склад (только Owner/Warehouse).",
)
async def receive_inventory(
    body: ReceiveStockInput,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    if current_user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(status_code=403, detail="Access denied")

    from app.services.store_service import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=404, detail="Главный склад не найден")

    from app.services.transaction_service import TransactionService
    txn_svc = TransactionService(session)
    
    try:
        inv = await txn_svc.receive_stock(
            warehouse_store_id=warehouse_id,
            product_id=body.product_id,
            quantity=body.quantity,
            user_id=current_user.id,
        )
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
        
    return {
        "success": True, 
        "product_id": inv.product_id, 
        "new_quantity": inv.quantity
    }


@router.post(
    "/bulk-receive",
    response_model=dict,
    summary="Массовый приход товара из Excel",
    description="Принимает список SKU и количеств, обновляет остатки на Главном Складе (Создаёт новые товары если их нет).",
)
async def bulk_receive_inventory(
    body: BulkReceiveInput,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    if current_user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(status_code=403, detail="Access denied")

    from app.services.store_service import StoreService
    from app.services.product_service import ProductService
    from app.services.transaction_service import TransactionService
    from app.models.product import Product
    
    store_svc = StoreService(session)
    product_svc = ProductService(session)
    txn_svc = TransactionService(session)
    
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=404, detail="Главный склад не найден")

    updated_count = 0
    created_count = 0
    
    try:
        for item in body.items:
            sku = item.sku.strip().upper()
            if not sku:
                raise HTTPException(status_code=400, detail="SKU cannot be empty")
            if item.quantity <= 0:
                raise HTTPException(status_code=400, detail=f"Invalid quantity for SKU {sku}")

            # Find product by SKU
            stmt = select(Product).where(Product.sku == sku)
            res = await session.execute(stmt)
            product = res.scalar_one_or_none()
            
            # Resolve effective brand: per-item brand is required
            effective_brand: str | None = (
                item.brand.strip() if item.brand and item.brand.strip()
                else (body.default_brand.strip() if body.default_brand else None)
            )
            if not effective_brand:
                raise HTTPException(
                    status_code=400,
                    detail=f"Фирма обязательна для товара SKU='{sku}'. Выберите фирму для каждого товара."
                )

            if not product:
                # Create new product
                price_val = Decimal(str(item.price)) if item.price is not None else Decimal(0)
                if price_val < 0:
                    raise HTTPException(status_code=400, detail=f"Invalid price for SKU {sku}")
                product = await product_svc.create_product(
                    sku=sku,
                    price=price_val,
                    brand=effective_brand,
                )
                created_count += 1
            else:
                # Update existing product — apply price and brand if provided
                if item.price is not None:
                    new_price = Decimal(str(item.price))
                    if new_price < 0:
                        raise HTTPException(status_code=400, detail=f"Invalid price for SKU {sku}")
                    product.price = new_price
                if effective_brand:
                    product.brand = effective_brand
                
            # Receive stock — replace or accumulate based on flag
            inv_stmt = select(Inventory).where(
                Inventory.store_id == warehouse_id,
                Inventory.product_id == product.id,
            )
            inv_res = await session.execute(inv_stmt)
            existing_inv = inv_res.scalar_one_or_none()

            if existing_inv:
                if body.replace_quantity:
                    existing_inv.quantity = item.quantity
                else:
                    existing_inv.quantity += item.quantity
            else:
                session.add(Inventory(
                    store_id=warehouse_id,
                    product_id=product.id,
                    quantity=item.quantity,
                ))
            updated_count += 1
            
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception("bulk_receive_inventory error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    
    return {
        "success": True,
        "processed": updated_count,
        "created": created_count,
    }


@router.post(
    "/dispatch-display",
    response_model=dict,
    summary="Отправить образцы (витрину) в магазин",
    description="Перемещает товар с Главного Склада в статус 'Образец' для магазина.",
)
async def dispatch_display(
    body: DispatchDisplayInput,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    if current_user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(status_code=403, detail="Access denied")

    from app.services.store_service import StoreService
    store_svc = StoreService(session)
    warehouse_id = await store_svc.get_main_warehouse_id()
    if not warehouse_id:
        raise HTTPException(status_code=404, detail="Главный склад не найден")

    from app.services.transaction_service import TransactionService
    txn_svc = TransactionService(session)
    
    try:
        display_order, wh_inv = await txn_svc.dispatch_display_items(
            warehouse_store_id=warehouse_id,
            target_store_id=body.target_store_id,
            product_id=body.product_id,
            quantity=body.quantity,
            user_id=current_user.id,
        )
        await session.commit()
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
    
    # Send notification to sellers
    try:
        from app.models.product import Product
        res = await session.execute(select(Product).where(Product.id == display_order.product_id))
        product = res.scalar_one()
        
        notif_svc = NotificationService(bot, session)
        await notif_svc.notify_sellers(
            store_id=display_order.store_id,
            text=lambda t: t("display_dispatched_seller_notif", sku=product.sku, qty=display_order.quantity),
            reply_markup=lambda t: InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t("btn_received"), 
                        callback_data=f"display:receive:{display_order.id}"
                    ),
                    InlineKeyboardButton(
                        text=t("btn_not_received"), 
                        callback_data=f"display:reject:{display_order.id}"
                    )
                ]
            ])
        )
    except Exception as exc:
        logger.error("Failed to send web dispatch notification: %s", exc)
        
    return {
        "success": True, 
        "order_id": display_order.id,
        "product_id": display_order.product_id, 
        "target_store_id": display_order.store_id,
        "quantity": display_order.quantity
    }


@router.post(
    "/import-vitrina",
    response_model=dict,
    summary="Массовая загрузка товаров на витрину",
    description="Принимает JSON со списком товаров и добавляет их в выбранный магазин (по 1 шт).",
)
async def import_vitrina_endpoint(
    body: BulkVitrinaInput,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict:
    if current_user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(status_code=403, detail="Access denied")

    from app.models.product import Product
    from app.services.store_service import StoreService
    
    store_svc = StoreService(session)
    
    store = await session.get(Store, body.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Указанный магазин/склад не найден")

    products_to_add = 0
    products_updated = 0
    qty_added = 0

    try:
        skus: set[str] = {item.sku for item in body.items}
        products_result = await session.execute(select(Product).where(Product.sku.in_(skus)))
        products_map: dict[str, Product] = {
            product.sku: product for product in products_result.scalars().all()
        }

        for item in body.items:
            sku = item.sku
            product = products_map.get(sku)
            if not product:
                product = Product(
                    sku=sku,
                    brand=item.brand,
                    price=Decimal("0.00"),
                    is_active=True,
                )
                session.add(product)
                products_map[sku] = product
                products_to_add += 1
            else:
                products_updated += 1

        await session.flush()

        inventory_model = DisplayInventory if store.store_type == StoreType.STORE else Inventory
        product_ids = list({product.id for product in products_map.values() if product.id is not None})
        
        inventory_map: dict[int, DisplayInventory | Inventory] = {}
        if product_ids:
            inventory_result = await session.execute(
                select(inventory_model).where(
                    inventory_model.store_id == store.id,
                    inventory_model.product_id.in_(product_ids),
                )
            )
            inventory_map = {
                inventory.product_id: inventory
                for inventory in inventory_result.scalars().all()
            }

        for item in body.items:
            product = products_map[item.sku]
            inventory = inventory_map.get(product.id)

            if not inventory:
                inventory = inventory_model(
                    store_id=store.id,
                    product_id=product.id,
                    quantity=1,
                )
                session.add(inventory)
                inventory_map[product.id] = inventory
                qty_added += 1
            else:
                if inventory.quantity == 0:
                    inventory.quantity = 1
                    qty_added += 1

        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")

    return {
        "success": True,
        "store": store.name,
        "created": products_to_add,
        "updated": products_updated,
        "added_qty": qty_added
    }
