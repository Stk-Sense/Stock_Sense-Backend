"""Unit tests for institutional data quality checks and gap detection."""

import pytest
from app.validate.quality import DataQualityError, validate_batch


def test_quality_valid_batch():
    tf_ms = 3600000  # 1h
    ts0 = 1704067200000
    ts1 = ts0 + tf_ms

    candles = [
        [ts0, 50000.0, 50500.0, 49800.0, 50200.0, 15.5],
        [ts1, 50200.0, 50300.0, 50100.0, 50250.0, 10.2],
    ]

    res = validate_batch(candles, "1h")
    assert len(res.valid_candles) == 2
    assert len(res.quarantined_candles) == 0
    assert res.duplicates_dropped == 0
    assert res.was_reordered is False
    assert len(res.gaps) == 0


def test_quality_rejects_malformed_columns_or_nan():
    # 5 columns instead of 6
    with pytest.raises(DataQualityError):
        validate_batch([[1704067200000, 100.0, 105.0, 95.0, 102.0]], "1h")

    # NaN value in close
    with pytest.raises(DataQualityError):
        validate_batch([[1704067200000, 100.0, 105.0, 95.0, float("nan"), 10.0]], "1h")


def test_quality_rejects_unaligned_timestamps():
    unaligned_ts = 1704067200000 + 500  # not divisible by 3,600,000
    with pytest.raises(DataQualityError):
        validate_batch([[unaligned_ts, 100.0, 105.0, 95.0, 102.0, 10.0]], "1h")


def test_quality_reordering_and_deduplication():
    tf_ms = 3600000
    ts0 = 1704067200000
    ts1 = ts0 + tf_ms
    ts2 = ts1 + tf_ms

    # Pass in out of order, with duplicate ts1
    candles = [
        [ts2, 102.0, 105.0, 101.0, 104.0, 10.0],
        [ts0, 100.0, 103.0, 99.0, 101.0, 5.0],
        [ts1, 101.0, 104.0, 100.0, 102.0, 8.0],
        [ts1, 101.0, 104.0, 100.0, 102.0, 8.0],  # duplicate
    ]

    res = validate_batch(candles, "1h")
    assert res.was_reordered is True
    assert res.duplicates_dropped == 1
    assert len(res.valid_candles) == 3
    assert [c[0] for c in res.valid_candles] == [ts0, ts1, ts2]


def test_quality_quarantines_insane_prices_and_volume():
    tf_ms = 3600000
    ts0 = 1704067200000
    ts1 = ts0 + tf_ms
    ts2 = ts1 + tf_ms

    candles = [
        [ts0, 100.0, 105.0, 95.0, 102.0, 10.0],  # Valid
        [ts1, 100.0, 90.0, 95.0, 102.0, 10.0],   # Insane: High (90) is lower than Open (100)
        [ts2, 100.0, 105.0, 95.0, 102.0, -5.0],   # Insane: Negative volume (-5)
    ]

    res = validate_batch(candles, "1h")
    assert len(res.valid_candles) == 1
    assert len(res.quarantined_candles) == 2
    assert res.quarantined_candles[0]["candle"][0] == ts1
    assert res.quarantined_candles[1]["candle"][0] == ts2


def test_quality_gap_detection_within_and_across_boundary():
    tf_ms = 3600000
    ts0 = 1704067200000
    # Missing ts0 + 1h
    ts2 = ts0 + (2 * tf_ms)
    # Missing ts2 + 1h, ts2 + 2h
    ts5 = ts2 + (3 * tf_ms)

    candles = [
        [ts2, 100.0, 105.0, 95.0, 102.0, 10.0],
        [ts5, 102.0, 107.0, 100.0, 105.0, 15.0],
    ]

    # Test gap across boundary from previous_last_ts (ts0)
    res = validate_batch(candles, "1h", previous_last_ts=ts0)
    assert len(res.gaps) == 2

    # Boundary gap: missing [ts0 + 1h, ts2)
    assert res.gaps[0] == (ts0 + tf_ms, ts2)
    # Internal gap: missing [ts2 + 1h, ts5)
    assert res.gaps[1] == (ts2 + tf_ms, ts5)
