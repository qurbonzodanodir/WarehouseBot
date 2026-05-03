# Warehouse Bot — Mini-ERP для сети магазинов обоев

## Tech Stack
- **Python 3.12+** | Пакеты: `uv`
- **Aiogram 3.x** — Telegram Bot (polling / webhook)
- **FastAPI** — Web framework (webhook endpoint + будущий REST API)
- **SQLAlchemy 2.0 Async** + **asyncpg** — ORM + PostgreSQL driver
- **Alembic** — Миграции БД
- **Pydantic Settings** — Конфигурация из `.env`
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
│   │   ├── reply.py        # Reply-клавиатуры:
│   │   │                   #   SELLER_MENU (Витрина, Заказ, Продажи, Ещё)
│   │   │                   #   SELLER_MORE_MENU (Отчет, Сделать возврат, Назад)
│   │   │                   #   WAREHOUSE_MENU (Приход, Образцы, Запросы, Остатки, Отгрузки)
│   │   │                   #   OWNER_MENU (Дашборд, Инкассация, Каталог, Управление)
│   │   └── inline.py       # Inline-кнопки (catalog_kb, product_select_kb, warehouse_return_kb и т.д.)
│   │                       #   catalog_kb принимает callback_prefix и item_callback_prefix
│   ├── states/states.py    # FSM: OrderFlow, SaleFlow, ReturnFlow, CashCollectionFlow,
│   │                       #   AddProductFlow, AddStockFlow, RegistrationFlow,
│   │                       #   AddStoreFlow, InviteFlow, ReceiveStockFlow, DisplayTransferFlow
│   └── routers/
│       ├── common.py       # /start (авто-регистрация owner + инвайт-код), /switch_role, /my_role
│       ├── seller.py       # Заказ товара, витрина, продажи, приемка, возврат, отчет
│       │                   #   ВАЖНО: содержит MENU_TEXTS set для защиты от конфликтов FSM
│       │                   #   Все menu-хендлеры вызывают state.clear()
│       └── warehouse/      # Пакет складщика (разбит по фичам)
│           ├── __init__.py     # Главный роутер, включает суб-роутеры
│           ├── orders.py       # 🔔 Запросы — отгрузка, отказ, ОДОБРЕНИЕ/ОТКЛОНЕНИЕ возврата
│           ├── receive.py      # 📥 Приход — FSM приёмки товара на склад
│           ├── display.py      # 📋 Образцы — отправка витринных рулонов в магазин
│           └── stock.py        # 📦 Остатки — просмотр остатков склада
│       └── owner/          # Пакет владельца (разбит по фичам)
│           ├── __init__.py     # Главный роутер, включает суб-роутеры
│           ├── dashboard.py    # 📊 Дашборд — статистика за день
│           ├── collection.py   # 💰 Инкассация — FSM сбор наличных
│           ├── catalog.py      # 📦 Каталог — просмотр/добавление товаров
│           ├── stock.py        # 📥 Пополнение склада — FSM
│           └── management.py   # ⚙️ Управление — магазины, сотрудники, инвайты, должники, рейтинг
├── core/
│   ├── config.py           # Pydantic Settings (BOT_TOKEN, DATABASE_URL, DEBUG, OWNER_TELEGRAM_ID)
│   └── database.py         # Async engine, session factory, Base
├── models/
│   ├── enums.py            # UserRole, OrderStatus, TransactionType (см. раздел Enums)
│   ├── user.py             # telegram_id (BigInt unique), role, store_id FK
│   ├── store.py            # name, address, current_debt
│   ├── product.py          # sku (unique), name, price
│   ├── inventory.py        # store_id + product_id (unique constraint), quantity
│   ├── order.py            # status lifecycle (см. ниже)
│   ├── transaction.py      # type: SALE/RETURN/CASH_COLLECTION, amount, product_id nullable
│   └── invite_code.py      # code (unique 6-char), role, store_id, expires_at, is_used
├── services/
│   ├── user_service.py         # get_user_by_telegram_id, list_users
│   ├── order_service.py        # create_order, dispatch_order, deliver_order, reject_order
│   │                           # get_store_inventory(session, store_id, include_empty=False)
│   ├── transaction_service.py  # record_sale, initiate_return, approve_return, reject_return
│   │                           # record_cash_collection
│   ├── notification_service.py # notify_warehouse, notify_sellers
│   ├── invite_service.py       # create_invite, get_invite_by_code, use_invite
│   └── store_service.py        # list_active_stores, create_store
└── (no schemas/ — removed)
```

## Enums (КРИТИЧЕСКИ ВАЖНО)

### OrderStatus
```python
class OrderStatus(str, enum.Enum):
    PENDING = "pending"        # Заказ создан продавцом
    DISPATCHED = "dispatched"  # Курьер отправлен складщиком
    DELIVERED = "delivered"    # Продавец принял товар
    REJECTED = "rejected"     # Складщик отклонил заказ
    SOLD = "sold"              # Продавец продал товар
    RETURNED = "returned"     # Возврат одобрен складом
    RETURN_PENDING = "return_pending"  # Возврат ожидает решения склада
```

### ⚠️ PostgreSQL Enum Case Sensitivity
**КРИТИЧЕСКАЯ ПРОБЛЕМА**: В PostgreSQL enum `order_status` исторически содержит значения
в РАЗНОМ регистре. Старые значения (`PENDING`, `DISPATCHED`) в UPPERCASE, а Python enum
использует lowercase (`"pending"`, `"sold"`). При добавлении НОВЫХ значений через Alembic
миграции нужно добавлять **ОБА** варианта регистра:

```python
# ПРАВИЛЬНО — всегда добавлять оба варианта:
op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'return_pending'")
op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'RETURN_PENDING'")
```

**Текущие значения в БД**: `PENDING`, `DISPATCHED`, `DELIVERED`, `REJECTED`,
`sold`, `returned`, `return_pending`, `RETURN_PENDING`, `SOLD`, `RETURNED`

### TransactionType
```python
class TransactionType(str, enum.Enum):
    SALE = "sale"
    RETURN = "return"
    CASH_COLLECTION = "cash_collection"
    DISPLAY_TRANSFER = "display_transfer"
    STOCK_RECEIVE = "stock_receive"
```

## Роли (3 шт)

| Роль | Enum | Меню |
|---|---|---|
| Продавец | `seller` | Витрина, Заказ, Продажи, Ещё (Отчет, Возврат) |
| Складчик | `warehouse` | Приход, Образцы, Запросы, Остатки, Отгрузки |
| Владелец | `owner` | Дашборд, Инкассация, Каталог, Управление |

## Регистрация (закрытая система)

1. **Первый владелец** — автоматически из `.env` (`OWNER_TELEGRAM_ID`). При первом `/start` создаётся пользователь с ролью `OWNER`.
2. **Сотрудники** — через инвайт-коды:
   - Владелец: ⚙️ Управление → 👥 Сотрудники → ➕ Пригласить → выбор магазина → роль → бот генерирует 6-значный код
   - Сотрудник: `/start` → вводит код → автоматическая регистрация с ролью и магазином
3. **Незнакомые пользователи** видят только: "🔒 Введите код приглашения"

## Бизнес-логика

### Сценарий: Заказ → Доставка → "Торговля с колес" (Sell from wheels)
**Особенность бизнеса**: Магазины (продавцы) физически не хранят запасов. Склад находится в 100 метрах. Когда клиент хочет купить товар:
1. Продавец берет деньги у клиента и сразу заказывает нужные товары со склада через бота.
2. Склад собирает корзину (Батч) и курьер привозит товар за 2-3 минуты.
3. Продавец принимает партию («✅ Принять всю партию»).
4. Так как клиент уже ждет, продавец нажимает **одну кнопку** «💰 Продать сразу всё (клиент ждет)», и бот автоматически списывает всю партию как проданную, вешая долг на магазин. Больше не нужно "кликать" продажу каждого товара поштучно.

### Сценарий: Возврат (2-шаговый)
**Важно**: Продавец может вернуть товар ДВУМЯ способами:
- Через кнопку "Ещё 🔽" → "↩️ Сделать возврат" (самостоятельный поиск по витрине)
- Через кнопку "↩️ Брак/Возврат" после приемки доставки (legacy, теперь перенаправляет)

**Шаг 1 — Инициация (продавец):**
1. Продавец ищет товар на витрине → выбирает → вводит количество
2. Создается `Order(RETURN_PENDING)` → товар списывается с витрины
3. Долг **НЕ** уменьшается
4. Складщик получает уведомление с кнопками "✅ Принять" / "❌ Отклонить"

**Шаг 2A — Одобрение (складщик):**
- Товар зачисляется на склад → `Transaction(RETURN)` → `current_debt` уменьшается → `Order(RETURNED)`
- Продавец получает уведомление: "Долг списан"

**Шаг 2B — Отказ (складщик):**
- Товар возвращается на витрину продавца → `Order(DELIVERED)` → долг не меняется
- Продавец получает уведомление: "Возврат отклонен"

### Сценарий: Образцы (display transfer)
1. Складщик: "📋 Образцы" → выбирает магазин → выбирает товар → количество
2. Товар списывается со склада, зачисляется в магазин
3. Долг **НЕ** увеличивается (это образцы, не продажа)

### Сценарий: Инкассация
1. Владелец нажимает «💰 Инкассация» → выбирает магазин с долгом
2. Вводит сумму (полная / частичная / пропуск)
3. `Transaction(CASH_COLLECTION)` → уменьшение `current_debt`

## Ключевые правила

### Бизнес
- Нельзя продать/вернуть товар, которого нет (проверка `quantity`)
- Мягкое удаление (`is_active = False`)
- Каталог (SKU, цены) управляется только владельцем

### Технические
- `server_default=func.now()` для `created_at`
- Транзакции автоматически открываются в `AuthMiddleware`. В роутерах используется `await session.commit()` (**нельзя** использовать `async with session.begin():`)
- **Eager loading обязательно**: при обращении к relationships в async-контексте всегда использовать `selectinload()` или `joinedload()`, иначе получите `MissingGreenlet`
- **FSM и меню-кнопки**: все handler'ы кнопок меню (Витрина, Продажи и т.д.) ДОЛЖНЫ вызывать `state.clear()` и фильтровать свой текст через `MENU_TEXTS` set, чтобы не конфликтовать с активным FSM search state
- **catalog_kb / product_select_kb**: при использовании для разных потоков (заказ, возврат) передавать `item_callback_prefix` чтобы callback_data кнопок совпадали с ожидаемым хендлером
- **PostgreSQL enums**: при добавлении новых значений через Alembic, добавлять ОБА регистра (см. раздел Enums)

## Переменные окружения (.env)
```
BOT_TOKEN=...
DATABASE_URL=postgresql+asyncpg://nodir@localhost:5432/warehouse_bot
DEBUG=true
OWNER_TELEGRAM_ID=6018112126
```

## БД
- PostgreSQL (localhost:5432, db: `warehouse_bot`)
- User: `nodir` (без пароля)
- Миграции: см. `alembic/versions/`

## Текущие данные
- Владелец: telegram_id `6018112126` (Nodir)
- Магазины: Главный склад (id=5), Магазин №1 (id=6)

## Запуск
```bash
uv run python main.py  # Канонический запуск: polling + FastAPI на порту 8030
```

- Каноническое FastAPI приложение: `app.api.app:app`
- `web/backend/main.py` сохранён только как совместимый алиас для старых импортов
