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
│   │   ├── reply.py        # Reply-клавиатуры (3 меню: seller, warehouse, owner)
│   │   └── inline.py       # Inline-кнопки (заказы, продажи, инкассация, каталог, управление)
│   ├── states/states.py    # FSM: OrderFlow, SaleFlow, ReturnFlow, CashCollectionFlow,
│   │                       #   AddProductFlow, AddStockFlow, RegistrationFlow,
│   │                       #   AddStoreFlow, InviteFlow
│   └── routers/
│       ├── common.py       # /start (авто-регистрация owner + инвайт-код), /switch_role, /my_role
│       ├── seller.py       # Заказ товара, остатки, продажа, приемка, отчет
│       ├── warehouse.py    # Активные запросы, отгрузка, отказ, остатки склада, история
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
│   ├── enums.py            # UserRole(SELLER,WAREHOUSE,ADMIN,OWNER), OrderStatus, TransactionType
│   ├── user.py             # telegram_id (BigInt unique), role, store_id FK
│   ├── store.py            # name, address, current_debt
│   ├── product.py          # sku (unique), name, price
│   ├── inventory.py        # store_id + product_id (unique constraint), quantity
│   ├── order.py            # status lifecycle: PENDING→DISPATCHED→DELIVERED/REJECTED
│   ├── transaction.py      # type: SALE/RETURN/CASH_COLLECTION, amount, product_id nullable
│   └── invite_code.py      # code (unique 6-char), role, store_id, expires_at, is_used
├── services/
│   ├── user_service.py     # get_user_by_telegram_id, list_users
│   ├── order_service.py    # create_order, dispatch_order, deliver_order, reject_order, inventory
│   ├── transaction_service.py  # record_sale, record_return, record_cash_collection
│   ├── invite_service.py   # create_invite, get_invite_by_code, use_invite
│   └── store_service.py    # list_active_stores, create_store
└── (no schemas/ — removed)
```

## Роли (3 шт)

| Роль | Enum | Меню |
|---|---|---|
| Продавец | `seller` | Заказ, остатки, продажа, отчет |
| Складчик | `warehouse` | Заявки, отгрузка, остатки склада, история |
| Владелец | `owner` | Дашборд, инкассация, каталог, управление системой |

> **Примечание**: В enum `UserRole` ещё есть `ADMIN` (для совместимости с БД), но в боте он не используется.

## Регистрация (закрытая система)

1. **Первый владелец** — автоматически из `.env` (`OWNER_TELEGRAM_ID`). При первом `/start` создаётся пользователь с ролью `OWNER`.
2. **Сотрудники** — через инвайт-коды:
   - Владелец: ⚙️ Управление → 👥 Сотрудники → ➕ Пригласить → выбор магазина → роль → бот генерирует 6-значный код
   - Сотрудник: `/start` → вводит код → автоматическая регистрация с ролью и магазином
3. **Незнакомые пользователи** видят только: "🔒 Введите код приглашения"
4. Команды `/register_owner` и `/add_user` **удалены**
5. `/switch_role` работает **только в DEBUG режиме**

## Бизнес-логика

### Сценарий: Заказ → Продажа
1. Продавец создает заказ → `Order(PENDING)`
2. Складчик подтверждает → списание со склада → `Order(DISPATCHED)` → уведомление продавцу
3. Продавец принимает → зачисление в магазин → `Order(DELIVERED)`
4. Продавец продает → списание из магазина → `Transaction(SALE)` → увеличение `current_debt`

### Сценарий: Инкассация
1. Владелец нажимает «💰 Инкассация» → выбирает магазин с долгом
2. Вводит сумму (полная / частичная / пропуск)
3. `Transaction(CASH_COLLECTION)` → уменьшение `current_debt`

## Ключевые правила
- Нельзя продать товар, которого нет (проверка `quantity`)
- Мягкое удаление (`is_active = False`)
- Каталог (SKU, цены) управляется только владельцем
- `server_default=func.now()` для `created_at`
- Транзакции автоматически открываются в `AuthMiddleware`. В роутерах используется `await session.commit()` (**нельзя** использовать `async with session.begin():`)

## Интерфейс владельца

### Reply-кнопки (внизу):
```
📊 Дашборд       | 💰 Инкассация
📦 Каталог       | 📥 Пополнить склад
         ⚙️ Управление
```

### ⚙️ Управление (inline-меню):
```
🏢 Магазины     | 👥 Сотрудники
📋 Должники     | 🏆 Рейтинг
```

## Команды бота
| Команда / Кнопка | Кто | Описание |
|---|---|---|
| `/start` | Все | Меню или ввод инвайт-кода |
| `/switch_role` | DEBUG | Сменить роль (только DEBUG) |
| `/my_role` | Все | Показать текущую роль |
| `/add_product` | Owner | Добавить товар (FSM) |
| `[📦 Каталог]` | Owner | Список товаров |
| `[📥 Пополнить склад]` | Owner | FSM по пополнению остатков |
| `[⚙️ Управление]` | Owner | Inline-меню управления |

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
- Миграции: `21a7a3b36c8e_initial_tables`, `b9aacd02643f_add_invite_codes`

## Текущие данные
- База данных чистая (без тестовых товаров)
- Владелец: telegram_id `6018112126` (Nodir)
- Магазины: Главный склад (5), Магазин №1 (6)

## Запуск
```bash
uv run python main.py  # Запуск polling + FastAPI на порту 8000
```
