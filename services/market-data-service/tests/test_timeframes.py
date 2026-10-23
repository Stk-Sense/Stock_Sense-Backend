"""Unit tests for timeframe utilities and timestamp alignments."""

import pytest
from app.ingest.timeframes import (
    tf_to_ms,
    align_timestamp_floor,
    align_timestamp_ceil,
    is_aligned,
    expected_candle_count,
    generate_expected_timestamps,
)


def test_tf_to_ms():
    assert tf_to_ms("1m") == 60_000
    assert tf_to_ms("5m") == 300_000
    assert tf_to_ms("15m") == 900_000
    assert tf_to_ms("1h") == 3_600_000
    assert tf_to_ms("4h") == 14_400_000
    assert tf_to_ms("1d") == 86_400_000

    with pytest.raises(ValueError):
        tf_to_ms("3d")


def test_alignments():
    tf_ms = 3_600_000  # 1h
    ts = 1700000000123
    floor_ts = align_timestamp_floor(ts, tf_ms)
    ceil_ts = align_timestamp_ceil(ts, tf_ms)

    assert floor_ts % tf_ms == 0
    assert ceil_ts % tf_ms == 0
    assert floor_ts <= ts
    assert ceil_ts >= ts
    assert is_aligned(floor_ts, tf_ms) is True
    assert is_aligned(ts, tf_ms) is False


def test_expected_candles():
    tf_ms = 3_600_000
    start = 1700000000000 - (1700000000000 % tf_ms)
    end = start + (10 * tf_ms)

    assert expected_candle_count(start, end, tf_ms) == 10
    timestamps = list(generate_expected_timestamps(start, end, tf_ms))
    assert len(timestamps) == 10
    assert timestamps[0] == start
    assert timestamps[-1] == end - tf_ms
