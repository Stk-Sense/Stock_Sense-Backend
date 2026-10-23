"""Health, readiness, and metrics endpoints."""

import os
import tempfile
from fastapi import APIRouter, Depends, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db import get_db
from common.errors import AppError, ErrorCode

router = APIRouter(tags=["Health & Observability"])


@router.get("/health", status_code=status.HTTP_200_OK)
def liveness() -> dict[str, str]:
    """Liveness probe indicating process is up."""
    return {"status": "ok"}


@router.get("/ready", status_code=status.HTTP_200_OK)
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness probe checking database connectivity and data store access."""
    # 1. Check DB connectivity
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(
            message=f"Database is not reachable: {exc}",
            code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # 2. Check Data Store write access
    try:
        os.makedirs(settings.DATA_STORE_DIR, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.DATA_STORE_DIR, delete=True) as tmp:
            tmp.write(b"healthcheck")
    except Exception as exc:
        raise AppError(
            message=f"Data store directory is not writable: {exc}",
            code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return {"status": "ready"}


@router.get("/metrics")
def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
