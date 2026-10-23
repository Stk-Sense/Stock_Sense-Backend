"""Unit tests for Syncer orchestration and incremental updates."""

from app.exchange.fake_client import FakeExchangeClient
from app.ingest.syncer import Syncer
from app.ingest.timeframes import tf_to_ms
from app.store.parquet_store import ParquetStore
from app.store.sync_repo import SyncRepository


def test_syncer_initial_and_idempotent_sync(temp_data_dir, test_db_session):
    exchange_client = FakeExchangeClient("test_binance")
    store = ParquetStore(temp_data_dir)
    syncer = Syncer(exchange_client, store, test_db_session)
    repo = SyncRepository(test_db_session)

    tf_ms = tf_to_ms("1h")
    # Base timestamp: 2024-01-01 00:00:00 UTC = 1704067200000
    start_ts = 1704067200000
    candle_count = 50

    # Seed 50 synthetic candles
    exchange_client.generate_synthetic_candles("BTC/USDT", "1h", start_ts, candle_count)

    simulated_now = start_ts + (candle_count + 5) * tf_ms

    # 1. First sync
    res1 = syncer.sync(
        symbol="BTC/USDT",
        timeframe="1h",
        requested_start=start_ts,
        current_time_ms=simulated_now,
    )

    assert res1["status"] == "DONE"
    assert res1["candles_added"] == 50
    assert res1["gaps_found"] == 0

    # Verify SyncState in DB
    state = repo.get_sync_state("test_binance", "BTC/USDT", "1h")
    assert state is not None
    assert state.first_ts == start_ts
    assert state.last_ts == start_ts + (49 * tf_ms)

    # 2. Re-run identical sync immediately (Idempotency test)
    res2 = syncer.sync(
        symbol="BTC/USDT",
        timeframe="1h",
        requested_start=start_ts,
        current_time_ms=simulated_now,
    )

    assert res2["status"] == "DONE"
    assert res2["candles_added"] == 0  # Zero duplicate candles added!


def test_syncer_incremental_append(temp_data_dir, test_db_session):
    exchange_client = FakeExchangeClient("test_binance")
    store = ParquetStore(temp_data_dir)
    syncer = Syncer(exchange_client, store, test_db_session)

    tf_ms = tf_to_ms("1h")
    start_ts = 1704067200000

    # Initial 20 candles
    exchange_client.generate_synthetic_candles("ETH/USDT", "1h", start_ts, 20)
    simulated_now_1 = start_ts + 25 * tf_ms

    res1 = syncer.sync(
        symbol="ETH/USDT",
        timeframe="1h",
        requested_start=start_ts,
        current_time_ms=simulated_now_1,
    )
    assert res1["candles_added"] == 20

    # Now simulate 10 more candles appearing later
    exchange_client.generate_synthetic_candles("ETH/USDT", "1h", start_ts, 30)
    simulated_now_2 = start_ts + 35 * tf_ms

    # Syncer should automatically pick up from last_ts + tf_ms
    res2 = syncer.sync(
        symbol="ETH/USDT",
        timeframe="1h",
        current_time_ms=simulated_now_2,
    )

    assert res2["status"] == "DONE"
    assert res2["candles_added"] == 10  # Only the 10 new candles were added!

    # Verify total in Parquet store
    candles = store.read_candles("test_binance", "ETH/USDT", "1h")
    assert len(candles) == 30
