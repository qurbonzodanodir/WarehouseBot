import sys
import os

# Allow imports from project root (app/, web/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.bot.bot import bot
from app.core.config import settings
from web.backend.routers import auth, orders, products, inventory, analytics, stores, finance, invites

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize bot session if needed (Aiogram Bot usually handles its own session)
    yield
    # Close bot session
    await bot.session.close()

app = FastAPI(
    title="Warehouse ERP — Web API",
    description=(
        "REST API для веб-интерфейса Warehouse ERP. "
        "Авторизация: POST /api/auth/login → Bearer token."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
API_PREFIX = "/api"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(orders.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(inventory.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(stores.router, prefix=API_PREFIX)
app.include_router(finance.router, prefix=API_PREFIX)
app.include_router(invites.router, prefix=API_PREFIX)


@app.get("/health", tags=["System"])
async def health() -> dict:
    return {"status": "ok", "service": "warehouse-web-api"}
