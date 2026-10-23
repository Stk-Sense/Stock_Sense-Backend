"""Unit tests for ParquetStore atomic merge-writes, partitioning, and queries."""

from pathlib import Path
from app.store.parquet_store import ParquetStore


def test_parquet_store_atomic_merge_and_deduplication(temp_data_dir):
    store = ParquetStore(temp_data_dir)
    exchange = "binance"
    symbol = "BTC/USDT"
    timeframe = "1h"

    # Batch 1: 3 candles in 2024
    # 2024-01-01 00:00:00 UTC = 1704067200000 ms
    ts0 = 1704067200000
    ts1 = ts0 + 3600000
    ts2 = ts1 + 3600000

    candles_1 = [
        [ts0, 42000.0, 42500.0, 41800.0, 42200.0, 10.5],
        [ts1, 42200.0, 42300.0, 42100.0, 42250.0, 8.2],
        [ts2, 42250.0, 42800.0, 42200.0, 42700.0, 15.0],
    ]

    added = store.write_candles(exchange, symbol, timeframe, candles_1)
    assert added == 3

    # Verify file was written
    partition_file = Path(temp_data_dir) / exchange / "BTC-USDT" / timeframe / "2024.parquet"
    assert partition_file.exists()

    # Verify no tmp files left
    tmp_files = list(partition_file.parent.glob(".*tmp*"))
    assert len(tmp_files) == 0

    # Batch 2: includes an existing candle (ts2 with updated close) and a new candle (ts3), out-of-order!
    ts3 = ts2 + 3600000
    candles_2 = [
        [ts3, 42700.0, 43000.0, 42600.0, 42900.0, 12.0],  # new
        [ts2, 42250.0, 42800.0, 42200.0, 42750.0, 15.5],  # duplicate with updated close
    ]

    added_2 = store.write_candles(exchange, symbol, timeframe, candles_2)
    assert added_2 == 1  # only ts3 was new!

    # Read back candles
    results = store.read_candles(exchange, symbol, timeframe)
    assert len(results) == 4
    # Verify strict ascending sort
    assert [r["ts"] for r in results] == [ts0, ts1, ts2, ts3]
    # Verify deduplication kept the latest values for ts2
    assert results[2]["close"] == 42750.0


def test_parquet_store_multi_year_partitioning(temp_data_dir):
    store = ParquetStore(temp_data_dir)
    exchange = "binance"
    symbol = "ETH/USDT"
    timeframe = "1d"

    # Candle in 2024 (2024-12-31 00:00:00 UTC = 1735603200000)
    ts_2024 = 1735603200000
    # Candle in 2025 (2025-01-01 00:00:00 UTC = 1735689600000)
    ts_2025 = 1735689600000

    candles = [
        [ts_2024, 2500.0, 2550.0, 2480.0, 2520.0, 100.0],
        [ts_2025, 2520.0, 2600.0, 2510.0, 2580.0, 150.0],
    ]

    added = store.write_candles(exchange, symbol, timeframe, candles)
    assert added == 2

    # Check both year files exist
    base_path = Path(temp_data_dir) / exchange / "ETH-USDT" / timeframe
    assert (base_path / "2024.parquet").exists()
    assert (base_path / "2025.parquet").exists()

    # Check coverage
    first_ts, last_ts, count = store.get_coverage(exchange, symbol, timeframe)
    assert first_ts == ts_2024
    assert last_ts == ts_2025
    assert count == 2


def test_parquet_store_range_query_and_limit(temp_data_dir):
    store = ParquetStore(temp_data_dir)
    exchange = "binance"
    symbol = "BTC/USDT"
    timeframe = "1h"

    base_ts = 1704067200000
    candles = [[base_ts + (i * 3600000), 100.0, 101.0, 99.0, 100.0, 1.0] for i in range(10)]
    store.write_candles(exchange, symbol, timeframe, candles)

    # Range: query 3 candles from index 2 to 5
    start_q = base_ts + (2 * 3600000)
    end_q = base_ts + (5 * 3600000)
    rows = store.read_candles(exchange, symbol, timeframe, start_ts=start_q, end_ts=end_q)
    assert len(rows) == 3
    assert rows[0]["ts"] == start_q
    assert rows[-1]["ts"] == end_q - 3600000

    # Limit: query with limit=2
    limited_rows = store.read_candles(exchange, symbol, timeframe, start_ts=start_q, limit=2)
    assert len(limited_rows) == 2
