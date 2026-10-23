"""Admin control endpoints for manual synchronization and job status."""

import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, status
from sqlalchemy.orm import Session

from app.config import settings
from app.exchange.ccxt_client import CCXTExchangeClient
from app.ingest.syncer import Syncer
from app.models.db import SessionLocal, get_db
from app.schemas.market import SyncInitiatedResponse, SyncRequest, SyncRunStatusResponse
from app.store.parquet_store import ParquetStore
from app.store.sync_repo import SyncRepository
from common.errors import AppError, ErrorCode
from common.logging import get_logger

logger = get_logger("admin_api")
router = APIRouter(prefix="/admin", tags=["Admin Synchronization"])


def verify_admin_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """Enforce service token authentication for admin endpoints."""
    if not x_api_key or x_api_key != settings.ADMIN_API_KEY:
        raise AppError(
            message="Invalid or missing X-API-Key header",
            code=ErrorCode.UNAUTHORIZED,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return x_api_key


def _run_background_sync(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    start_ts: Optional[int],
    end_ts: Optional[int],
    run_id: uuid.UUID,
) -> None:
    """Execute syncer in a background worker with fresh DB session and client."""
    db = SessionLocal()
    client = CCXTExchangeClient(exchange_id)
    store = ParquetStore(settings.DATA_STORE_DIR)
    syncer = Syncer(client, store, db)
    try:
        syncer.sync(
            symbol=symbol,
            timeframe=timeframe,
            requested_start=start_ts,
            requested_end=end_ts,
            run_id=run_id,
        )
    finally:
        client.close()
        db.close()


@router.post("/sync", response_model=SyncInitiatedResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(verify_admin_key),
    db: Session = Depends(get_db),
) -> SyncInitiatedResponse:
    """Trigger an incremental or historical market data sync in the background."""
    run_id = uuid.uuid4()
    repo = SyncRepository(db)

    # Queue run record immediately
    repo.create_sync_run(
        exchange=settings.EXCHANGE_ID,
        symbol=request.symbol,
        timeframe=request.timeframe,
        requested_start=request.start_ts,
        requested_end=request.end_ts,
        run_id=run_id,
    )

    # Schedule background execution
    background_tasks.add_task(
        _run_background_sync,
        settings.EXCHANGE_ID,
        request.symbol,
        request.timeframe,
        request.start_ts,
        request.end_ts,
        run_id,
    )

    return SyncInitiatedResponse(run_id=run_id, status="QUEUED", message="Sync job initiated")


@router.get("/sync/{run_id}", response_model=SyncRunStatusResponse)
def get_sync_status(
    run_id: uuid.UUID,
    _: str = Depends(verify_admin_key),
    db: Session = Depends(get_db),
) -> SyncRunStatusResponse:
    """Query the execution status and metrics of a sync run."""
    repo = SyncRepository(db)
    run = repo.get_sync_run(run_id)

    if not run:
        raise AppError(
            message=f"Sync run with ID '{run_id}' not found",
            code=ErrorCode.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return SyncRunStatusResponse(
        run_id=run.id,
        exchange=run.exchange,
        symbol=run.symbol,
        timeframe=run.timeframe,
        status=run.status,
        candles_added=run.candles_added,
        gaps_found=run.gaps_found,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )
