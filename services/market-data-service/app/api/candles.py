"""Candles query endpoint serving columnar JSON with cursor pagination."""

from typing import Optional
from fastapi import APIRouter, Query, status

from app.config import settings
from app.ingest.timeframes import tf_to_ms
from app.schemas.market import ColumnarCandlesResponse
from app.store.parquet_store import ParquetStore
from common.errors import AppError, ErrorCode

router = APIRouter(tags=["Market Data"])


@router.get("/candles", response_model=ColumnarCandlesResponse)
def get_candles(
    symbol: str = Query(..., description="Pair symbol (e.g. BTC/USDT)"),
    timeframe: str = Query(..., description="Candle timeframe (e.g. 1h, 1d)"),
    start: Optional[int] = Query(None, description="Start timestamp in epoch milliseconds (inclusive)"),
    end: Optional[int] = Query(None, description="End timestamp in epoch milliseconds (exclusive)"),
    limit: int = Query(default=1000, ge=1, le=5000, description="Max candles to return (capped at 5000)"),
) -> ColumnarCandlesResponse:
    """Retrieve historical OHLCV candle data in columnar format."""
    # 1. Validate timeframe
    try:
        tf_ms = tf_to_ms(timeframe)
    except ValueError as exc:
        raise AppError(
            message=str(exc),
            code=ErrorCode.INVALID_INPUT,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Validate range
    if start is not None and end is not None and start >= end:
        raise AppError(
            message=f"Invalid range: start timestamp ({start}) must be strictly less than end ({end})",
            code=ErrorCode.INVALID_INPUT,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    store = ParquetStore(settings.DATA_STORE_DIR)
    records = store.read_candles(
        exchange=settings.EXCHANGE_ID,
        symbol=symbol,
        timeframe=timeframe,
        start_ts=start,
        end_ts=end,
        limit=limit,
    )

    columns = ["ts", "open", "high", "low", "close", "volume"]
    data = [[r["ts"], r["open"], r["high"], r["low"], r["close"], r["volume"]] for r in records]

    next_cursor = None
    if len(records) == limit and records:
        # Cursor for next page: last returned timestamp + 1 timeframe
        last_ts = int(records[-1]["ts"])
        next_cursor = last_ts + tf_ms

    return ColumnarCandlesResponse(
        symbol=symbol,
        timeframe=timeframe,
        columns=columns,
        data=data,
        count=len(data),
        next_cursor=next_cursor,
    )
