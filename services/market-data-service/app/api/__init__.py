"""API router configuration."""

from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.candles import router as candles_router
from app.api.health import router as health_router
from app.api.status import router as status_router
from app.api.symbols import router as symbols_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health_router)
api_router.include_router(symbols_router)
api_router.include_router(candles_router)
api_router.include_router(status_router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
