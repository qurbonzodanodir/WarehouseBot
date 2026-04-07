from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.display_inventory import DisplayInventory
from app.models.inventory import Inventory
from app.models.enums import UserRole
from app.models.store import Store
from web.backend.dependencies import CurrentUser, SessionDep
from web.backend.schemas.stores import InventoryItemOut, ReceiveStockInput, BulkReceiveInput, DispatchDisplayInput
from app.bot.bot import bot
from app.services.notification_service import NotificationService
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)
# ... (lines 12-19)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get(
    "/{store_id}",
    response_model=list[InventoryItemOut],
    summary="Остатки магазина / склада",
    description="Возвращает товары с количеством для указанного магазина (включая витрину).",
)
async def get_store_inventory(
    store_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    include_empty: bool = Query(False),
) -> list[InventoryItemOut]:
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

    # Combine
    out = []
    for inv in items_reg:
        out.append(InventoryItemOut(
            product_id=inv.product_id,
            product_sku=inv.product.sku,
            quantity=inv.quantity,
            is_display=False
        ))
    
    for inv in items_disp:
        out.append(InventoryItemOut(
            product_id=inv.product_id,
            product_sku=inv.product.sku,
            quantity=inv.quantity,
            is_display=True
        ))

    return out


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

    stores_result = await session.execute(
        select(Store).where(Store.is_active.is_(True))
    )
    stores = stores_result.scalars().all()

    result = {}
    for store in stores:
        # Regular
        stmt_reg = (
            select(Inventory)
            .options(joinedload(Inventory.product))
            .where(Inventory.store_id == store.id, Inventory.quantity > 0)
        )
        res_reg = await session.execute(stmt_reg)
        items_reg = res_reg.scalars().all()

        # Display
        stmt_disp = (
            select(DisplayInventory)
            .options(joinedload(DisplayInventory.product))
            .where(DisplayInventory.store_id == store.id, DisplayInventory.quantity > 0)
        )
        res_disp = await session.execute(stmt_disp)
        items_disp = res_disp.scalars().all()

        store_items = []
        for inv in items_reg:
            store_items.append({
                "product_id": inv.product_id,
                "sku": inv.product.sku,
                "quantity": inv.quantity,
                "is_display": False
            })
        for inv in items_disp:
            store_items.append({
                "product_id": inv.product_id,
                "sku": inv.product.sku,
                "quantity": inv.quantity,
                "is_display": True
            })

        result[store.id] = {
            "store_name": store.name,
            "items": store_items,
        }

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
            
            if not product:
                # Create new product
                price_val = Decimal(str(item.price)) if item.price is not None else Decimal(0)
                if price_val < 0:
                    raise HTTPException(status_code=400, detail=f"Invalid price for SKU {sku}")
                product = await product_svc.create_product(
                    sku=sku,
                    price=price_val,
                )
                created_count += 1
            elif item.price is not None:
                # Update existing product price
                new_price = Decimal(str(item.price))
                if new_price < 0:
                    raise HTTPException(status_code=400, detail=f"Invalid price for SKU {sku}")
                product.price = new_price
                
            # Receive stock
            await txn_svc.receive_stock(
                warehouse_store_id=warehouse_id,
                product_id=product.id,
                quantity=item.quantity,
                user_id=current_user.id,
            )
            updated_count += 1
            
        await session.commit()
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
    
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
