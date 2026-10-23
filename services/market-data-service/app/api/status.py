"""Data coverage and sync health status endpoint."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.ingest.timeframes import tf_to_ms
from app.models.db import get_db
from app.schemas.market import DataStatusResponse
from app.store.parquet_store import ParquetStore
from app.store.sync_repo import SyncRepository
from common.errors import AppError, ErrorCode

router = APIRouter(tags=["Market Catalog"])


@router.get("/data-status", response_model=DataStatusResponse)
def get_data_status(
    symbol: str = Query(..., description="Pair symbol (e.g. BTC/USDT)"),
    timeframe: str = Query(..., description="Candle timeframe (e.g. 1h, 1d)"),
    db: Session = Depends(get_db),
) -> DataStatusResponse:
    """Retrieve coverage status, record counts, and synchronization health."""
    try:
        tf_to_ms(timeframe)
    except ValueError as exc:
        raise AppError(
            message=str(exc),
            code=ErrorCode.INVALID_INPUT,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    repo = SyncRepository(db)
    store = ParquetStore(settings.DATA_STORE_DIR)

    state = repo.get_sync_state(settings.EXCHANGE_ID, symbol, timeframe)
    disk_first, disk_last, disk_count = store.get_coverage(settings.EXCHANGE_ID, symbol, timeframe)

    first_ts = disk_first if disk_first is not None else (state.first_ts if state else None)
    last_ts = disk_last if disk_last is not None else (state.last_ts if state else None)
    total_candles = disk_count
    sync_status = state.status if state else "IDLE"
    last_updated = state.updated_at if state else None

    return DataStatusResponse(
        exchange=settings.EXCHANGE_ID,
        symbol=symbol,
        timeframe=timeframe,
        first_ts=first_ts,
        last_ts=last_ts,
        total_candles=total_candles,
        status=sync_status,
        last_updated_at=last_updated,
    )
