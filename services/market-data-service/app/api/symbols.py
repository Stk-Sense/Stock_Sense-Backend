"""Symbols and coverage catalog endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db import get_db
from app.schemas.market import SymbolCoverage, SymbolsResponse
from app.store.parquet_store import ParquetStore
from app.store.sync_repo import SyncRepository

router = APIRouter(tags=["Market Catalog"])


@router.get("/symbols", response_model=SymbolsResponse)
def get_symbols(db: Session = Depends(get_db)) -> SymbolsResponse:
    """List available trading symbols, timeframes, and date coverage."""
    store = ParquetStore(settings.DATA_STORE_DIR)
    repo = SyncRepository(db)

    # Combine symbols from config and stored data
    known_symbols = set(settings.DEFAULT_SYMBOLS)
    stored_symbols = store.list_available_symbols(settings.EXCHANGE_ID)
    all_symbols = sorted(known_symbols.union(stored_symbols))

    coverages: list[SymbolCoverage] = []

    for sym in all_symbols:
        available_tfs = store.list_available_timeframes(settings.EXCHANGE_ID, sym)
        if not available_tfs:
            available_tfs = settings.DEFAULT_TIMEFRAMES

        overall_first: int | None = None
        overall_last: int | None = None
        total_candles = 0

        for tf in available_tfs:
            f_ts, l_ts, count = store.get_coverage(settings.EXCHANGE_ID, sym, tf)
            if f_ts is not None:
                if overall_first is None or f_ts < overall_first:
                    overall_first = f_ts
            if l_ts is not None:
                if overall_last is None or l_ts > overall_last:
                    overall_last = l_ts
            total_candles += count

        coverages.append(
            SymbolCoverage(
                symbol=sym,
                timeframes=available_tfs,
                first_ts=overall_first,
                last_ts=overall_last,
                candle_count=total_candles,
            )
        )

    return SymbolsResponse(exchange=settings.EXCHANGE_ID, symbols=coverages)
