# Warehouse Bot — Mini-ERP для сети магазинов

## Tech Stack
- **Python 3.12+** | Пакеты: `uv`
- **Aiogram 3.x** — Telegram Bot (polling / webhook)
- **FastAPI** — Web framework (webhook endpoint + будущий REST API)
- **SQLAlchemy 2.0 Async** + **asyncpg** — ORM + PostgreSQL driver
- **Alembic** — Миграции БД
- **Pydantic Settings** — Конфигурация из `.env`
- **APScheduler** — Фоновые задачи (пока не реализован)
- **FSM**: `MemoryStorage` (Aiogram, без Redis)

## Архитектура

```
app/
├── api/app.py              # FastAPI — webhook + health, dual-mode (polling/webhook)
├── bot/
│   ├── bot.py              # Bot + Dispatcher factory, подключение роутеров
│   ├── filters.py          # RoleFilter — фильтр по ролям
│   ├── middlewares/auth.py  # AuthMiddleware — lookup user по telegram_id
│   ├── keyboards/
│   │   ├── reply.py        # Reply-клавиатуры (3 меню: seller, warehouse, owner)
│   │   └── inline.py       # Inline-кнопки (заказы, продажи, инкассация, каталог)
│   ├── states/states.py    # FSM: OrderFlow, SaleFlow, ReturnFlow, CashCollectionFlow
│   └── routers/
│       ├── common.py       # /start, /register_owner, /add_user, /switch_role, /my_role
│       ├── seller.py       # Заказ товара, остатки, продажа, приемка, отчет
│       ├── warehouse.py    # Активные запросы, отгрузка, отказ, остатки склада, история
│       └── owner.py        # Дашборд, рейтинг, популярные товары, настройки,
│                           # инкассация, должники, /add_product, /add_store, /add_stock
├── core/
│   ├── config.py           # Pydantic Settings (BOT_TOKEN, DATABASE_URL, DEBUG)
│   └── database.py         # Async engine, session factory, Base
├── models/
│   ├── enums.py            # UserRole(SELLER,WAREHOUSE,ADMIN,OWNER), OrderStatus, TransactionType
│   ├── user.py             # telegram_id (BigInt unique), role, store_id FK
│   ├── store.py            # name, address, current_debt
│   ├── product.py          # sku (unique), name, price
│   ├── inventory.py        # store_id + product_id (unique constraint), quantity
│   ├── order.py            # status lifecycle: PENDING→DISPATCHED→DELIVERED/REJECTED
│   └── transaction.py      # type: SALE/RETURN/CASH_COLLECTION, amount, product_id nullable
├── services/
│   ├── user_service.py     # get_user_by_telegram_id, list_users
│   ├── order_service.py    # create_order, dispatch_order, deliver_order, reject_order, inventory
│   └── transaction_service.py  # record_sale, record_return, record_cash_collection
└── schemas/                # Pydantic schemas (TODO)
```

## Роли (3 шт)

| Роль | Enum | Меню |
|---|---|---|
| Продавец | `seller` | Заказ, остатки, продажа, отчет |
| Складчик | `warehouse` | Заявки, отгрузка, остатки склада, история |
| Владелец | `owner` | Дашборд, аналитика, инкассация, управление каталогом/сотрудниками |

> **Примечание**: В enum `UserRole` ещё есть `ADMIN` (для совместимости с БД), но в боте он не используется — функции админа (инкассация) объединены с ролью владельца.

## Бизнес-логика

### Сценарий: Заказ → Продажа
1. Продавец создает заказ → `Order(PENDING)`
2. Складчик подтверждает → списание со склада → `Order(DISPATCHED)` → уведомление продавцу
3. Продавец принимает → зачисление в магазин → `Order(DELIVERED)`
4. Продавец продает → списание из магазина → `Transaction(SALE)` → увеличение `current_debt`

### Сценарий: Инкассация
1. Владелец выбирает магазин с долгом
2. Вводит сумму (полная / частичная / пропуск)
3. `Transaction(CASH_COLLECTION)` → уменьшение `current_debt`

## Ключевые правила
- Нельзя продать товар, которого нет (проверка `quantity`)
- Мягкое удаление (`is_active = False`)
- Каталог (SKU, цены) управляется только владельцем
- `server_default=func.now()` для `created_at`
- Все операции через `async with session.begin():` (атомарные транзакции)

## Команды бота
| Команда | Кто | Описание |
|---|---|---|
| `/start` | Все | Показать меню или регистрацию |
| `/register_owner` | Новый | Саморегистрация владельца (один раз) |
| `/add_user <tg_id> <role> <store_id> <name>` | Owner | Добавить сотрудника |
| `/switch_role <role> <store_id>` | Все | Сменить роль (для тестов) |
| `/my_role` | Все | Показать текущую роль |
| `/add_product <sku> <price> <name>` | Owner | Добавить товар |
| `/add_store <name> \| <address>` | Owner | Добавить магазин |
| `/add_stock <store_id> <sku> <qty>` | Owner | Пополнить остатки |
| `/products` | Owner | Список товаров |
| `/stores` | Owner | Список магазинов |

## БД
- PostgreSQL (localhost:5432, db: `warehouse_bot`)
- User: `nodir` (без пароля)
- Alembic миграция: `21a7a3b36c8e_initial_tables`

## Тестовые данные
- Магазины: Главный склад (5), Магазин №1 (6), Магазин №2 (7)
- Товары: OB-123, OB-456, BG-001
- Владелец: telegram_id `6018112126`

## Запуск
```bash
uv run python main.py  # Запуск polling + FastAPI на порту 8000
```
