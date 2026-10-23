"""Pydantic DTO schemas for API request and response models."""

import uuid
from datetime import datetime
from typing import Any, Optional, Union
from pydantic import BaseModel, Field


class SymbolCoverage(BaseModel):
    symbol: str
    timeframes: list[str]
    first_ts: Optional[int] = None
    last_ts: Optional[int] = None
    candle_count: int = 0


class SymbolsResponse(BaseModel):
    exchange: str
    symbols: list[SymbolCoverage]


class ColumnarCandlesResponse(BaseModel):
    symbol: str
    timeframe: str
    columns: list[str] = ["ts", "open", "high", "low", "close", "volume"]
    data: list[list[Union[int, float]]]
    count: int
    next_cursor: Optional[int] = None


class DataStatusResponse(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    first_ts: Optional[int] = None
    last_ts: Optional[int] = None
    total_candles: int = 0
    status: str = "IDLE"
    last_updated_at: Optional[datetime] = None


class SyncRequest(BaseModel):
    symbol: str = Field(..., json_schema_extra={"example": "BTC/USDT"})
    timeframe: str = Field(..., json_schema_extra={"example": "1h"})
    start_ts: Optional[int] = Field(None, description="Starting epoch timestamp in milliseconds")
    end_ts: Optional[int] = Field(None, description="Ending epoch timestamp in milliseconds")


class SyncInitiatedResponse(BaseModel):
    run_id: uuid.UUID
    status: str = "QUEUED"
    message: str = "Sync job initiated"


class SyncRunStatusResponse(BaseModel):
    run_id: uuid.UUID
    exchange: str
    symbol: str
    timeframe: str
    status: str
    candles_added: int = 0
    gaps_found: int = 0
    error: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
