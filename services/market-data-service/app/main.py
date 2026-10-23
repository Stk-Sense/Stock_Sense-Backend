"""FastAPI application factory, lifespan, and middleware setup."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import settings
from app.models.db import init_db
from app.scheduler import scheduler
from common.errors import AppError, ErrorCode, ErrorDetail, ErrorResponse
from common.logging import configure_logging, get_correlation_id, get_logger
from common.middleware import CorrelationIdMiddleware

configure_logging(settings.LOG_LEVEL)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    logger.info("Initializing StockSense Market Data Service...")
    # Initialize DB tables
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.warning(f"Database initialization warning (will retry on requests): {exc}")

    # Start background scheduler if enabled
    if settings.ENABLE_SCHEDULER:
        try:
            scheduler.start()
        except Exception as exc:
            logger.error(f"Failed to start scheduler: {exc}")

    yield

    logger.info("Shutting down Market Data Service...")
    scheduler.shutdown()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    application = FastAPI(
        title="StockSense Market Data Service",
        description="Institutional-grade cryptocurrency historical and incremental OHLCV market data service",
        version="1.0.0",
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs",
        redoc_url="/v1/redoc",
        lifespan=lifespan,
    )

    # Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(CorrelationIdMiddleware)

    # Exception Handlers
    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        error_resp = ErrorResponse(
            error=ErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details if exc.details else None,
            ),
            correlation_id=get_correlation_id(),
        )
        return JSONResponse(status_code=exc.status_code, content=error_resp.model_dump())

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled server exception: {exc}")
        error_resp = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.INTERNAL_ERROR,
                message="An unexpected internal error occurred",
            ),
            correlation_id=get_correlation_id(),
        )
        return JSONResponse(status_code=500, content=error_resp.model_dump())

    # Include routes
    application.include_router(api_router)

    return application


app = create_app()
