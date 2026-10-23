"""Timeframe resolution, millisecond conversions, and alignment helpers."""

from typing import Iterable

TIMEFRAME_TO_MS: dict[str, int] = {
    "1m": 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


def tf_to_ms(timeframe: str) -> int:
    """Convert a timeframe string (e.g. '1h', '1d', '15m') to milliseconds.

    Raises:
        ValueError: If timeframe is not supported.
    """
    if timeframe not in TIMEFRAME_TO_MS:
        raise ValueError(f"Unsupported timeframe '{timeframe}'. Supported: {list(TIMEFRAME_TO_MS.keys())}")
    return TIMEFRAME_TO_MS[timeframe]


def align_timestamp_floor(ts: int, tf_ms: int) -> int:
    """Round timestamp down to the nearest multiple of tf_ms."""
    return (ts // tf_ms) * tf_ms


def align_timestamp_ceil(ts: int, tf_ms: int) -> int:
    """Round timestamp up to the nearest multiple of tf_ms."""
    if ts % tf_ms == 0:
        return ts
    return ((ts // tf_ms) + 1) * tf_ms


def is_aligned(ts: int, tf_ms: int) -> bool:
    """Check if a timestamp is strictly aligned with the timeframe interval."""
    return ts % tf_ms == 0


def expected_candle_count(start_ts: int, end_ts: int, tf_ms: int) -> int:
    """Calculate expected number of candles in [start_ts, end_ts)."""
    if end_ts <= start_ts:
        return 0
    return (end_ts - start_ts) // tf_ms


def generate_expected_timestamps(start_ts: int, end_ts: int, tf_ms: int) -> Iterable[int]:
    """Generate expected timestamps from start_ts up to end_ts (exclusive)."""
    curr = align_timestamp_floor(start_ts, tf_ms)
    while curr < end_ts:
        yield curr
        curr += tf_ms
