from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.catalog import router as catalog_router
from app.api.store import cart_router, orders_router, preferences_router, router as store_router
from app.core.config import get_settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Освобождает пул соединений при остановке приложения."""
    yield
    await engine.dispose()


settings = get_settings()
settings.uploads_path.mkdir(parents=True, exist_ok=True)
app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Telegram-Init-Data"],
)
app.include_router(catalog_router)
app.include_router(admin_router)
app.include_router(store_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(preferences_router)
app.mount(
    "/uploads",
    StaticFiles(directory=settings.uploads_path),
    name="uploaded-images",
)


@app.get("/health", tags=["Состояние"], summary="Проверка работоспособности")
async def health_check() -> dict[str, str]:
    """Проверяет доступность процесса API."""
    return {"status": "ok"}
