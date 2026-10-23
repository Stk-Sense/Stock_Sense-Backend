"""Unit tests for Downloader engine with pagination and forming-candle protection."""

import pytest
from app.exchange.fake_client import FakeExchangeClient
from app.ingest.downloader import Downloader
from app.ingest.timeframes import tf_to_ms


def test_downloader_pagination():
    fake = FakeExchangeClient("fake_binance")
    downloader = Downloader(fake)

    tf_ms = tf_to_ms("1h")
    start_ts = 1700000000000 - (1700000000000 % tf_ms)
    count = 2500  # 2.5 batches with batch_limit=1000

    # Seed 2500 synthetic candles
    fake.generate_synthetic_candles("BTC/USDT", "1h", start_ts, count)

    # Pretend current time is far ahead in the future
    now_ms = start_ts + (count + 10) * tf_ms

    batches = list(downloader.fetch_batches(
        symbol="BTC/USDT",
        timeframe="1h",
        start_ts=start_ts,
        batch_limit=1000,
        current_time_ms=now_ms,
    ))

    assert len(batches) == 3
    assert len(batches[0]) == 1000
    assert len(batches[1]) == 1000
    assert len(batches[2]) == 500

    total_candles = sum(len(b) for b in batches)
    assert total_candles == 2500


def test_downloader_forming_candle_exclusion():
    fake = FakeExchangeClient("fake_binance")
    downloader = Downloader(fake)

    tf_ms = tf_to_ms("1h")
    start_ts = 1700000000000 - (1700000000000 % tf_ms)

    # 3 candles:
    # candle 0: closed (ts + tf_ms <= now)
    # candle 1: closed (ts + tf_ms <= now)
    # candle 2: currently forming! (ts <= now < ts + tf_ms)
    c0_ts = start_ts
    c1_ts = start_ts + tf_ms
    c2_ts = start_ts + (2 * tf_ms)

    # Simulated now: halfway through candle 2
    simulated_now = c2_ts + (15 * 60 * 1000)

    fake.set_candles("BTC/USDT", "1h", [
        [c0_ts, 100.0, 105.0, 99.0, 104.0, 10.0],
        [c1_ts, 104.0, 108.0, 103.0, 107.0, 12.0],
        [c2_ts, 107.0, 109.0, 106.0, 108.0, 5.0],  # Still forming!
    ])

    batches = list(downloader.fetch_batches(
        symbol="BTC/USDT",
        timeframe="1h",
        start_ts=start_ts,
        current_time_ms=simulated_now,
    ))

    # All returned candles must have ts + tf_ms <= simulated_now
    returned_candles = [c for b in batches for c in b]
    assert len(returned_candles) == 2
    assert returned_candles[0][0] == c0_ts
    assert returned_candles[1][0] == c1_ts
    # Candle 2 must be excluded!
    assert all(c[0] != c2_ts for c in returned_candles)


def test_downloader_empty_exchange_response():
    fake = FakeExchangeClient("fake_binance")
    downloader = Downloader(fake)

    batches = list(downloader.fetch_batches(
        symbol="UNKNOWN/PAIR",
        timeframe="1h",
        start_ts=1700000000000,
    ))

    assert len(batches) == 0
