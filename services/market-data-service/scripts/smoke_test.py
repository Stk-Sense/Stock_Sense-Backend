"""Live exchange smoke test script.

Tests downloading, validating, and storing real OHLCV candles from an active exchange.
"""

import sys
import tempfile
import time
from app.exchange.ccxt_client import CCXTExchangeClient
from app.ingest.downloader import Downloader
from app.ingest.timeframes import tf_to_ms
from app.store.parquet_store import ParquetStore
from app.validate.quality import validate_batch


def run_smoke_test(exchange_id: str = "kraken", symbol: str = "BTC/USDT", timeframe: str = "1h") -> None:
    print(f"=== Starting live smoke test for {exchange_id.upper()} {symbol} {timeframe} ===")
    tf_ms = tf_to_ms(timeframe)
    client = CCXTExchangeClient(exchange_id, max_retries=3)

    try:
        # Step 1: Live connection & fetch markets
        print("1. Fetching available markets...")
        markets = client.fetch_markets()
        print(f"   Success! Found {len(markets)} markets on {exchange_id}.")

        # Step 2: Live OHLCV fetch via Downloader
        print("2. Downloading live candle batches...")
        downloader = Downloader(client)
        now_ms = int(time.time() * 1000)
        # Fetch last 7 days of 1h candles (7 * 24 = 168 candles)
        start_ts = now_ms - (7 * 24 * 60 * 60 * 1000)
        start_ts = (start_ts // tf_ms) * tf_ms

        batches = list(downloader.fetch_batches(
            symbol=symbol,
            timeframe=timeframe,
            start_ts=start_ts,
            batch_limit=500,
            current_time_ms=now_ms,
        ))

        all_candles = [c for b in batches for c in b]
        print(f"   Success! Fetched {len(all_candles)} closed candles.")
        if not all_candles:
            print("   Warning: No candles returned.")
            return

        # Step 3: Forming candle verification
        latest_ts = int(all_candles[-1][0])
        print(f"   Latest candle timestamp: {latest_ts}")
        assert latest_ts + tf_ms <= now_ms, "Forming candle leak detected! Latest candle is not closed."
        print("   Forming-candle check passed (no look-ahead leak).")

        # Step 4: Quality validation
        print("3. Validating data quality...")
        val_res = validate_batch(all_candles, timeframe=timeframe)
        print(f"   Valid candles: {len(val_res.valid_candles)}")
        print(f"   Quarantined: {len(val_res.quarantined_candles)}")
        print(f"   Duplicates dropped: {val_res.duplicates_dropped}")
        print(f"   Detected gaps: {len(val_res.gaps)}")

        # Step 5: Parquet atomic storage
        print("4. Testing atomic Parquet store...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = ParquetStore(tmp_dir)
            added = store.write_candles(exchange_id, symbol, timeframe, val_res.valid_candles)
            print(f"   Successfully wrote {added} candles to Parquet.")

            # Step 6: Query back & verify
            read_back = store.read_candles(exchange_id, symbol, timeframe)
            print(f"   Read back {len(read_back)} candles from Parquet.")
            assert len(read_back) == len(val_res.valid_candles)

            f_ts, l_ts, count = store.get_coverage(exchange_id, symbol, timeframe)
            print(f"   Coverage: first_ts={f_ts}, last_ts={l_ts}, count={count}")

        print("=== Live smoke test completed successfully! ===")

    finally:
        client.close()


if __name__ == "__main__":
    ex = sys.argv[1] if len(sys.argv) > 1 else "kraken"
    run_smoke_test(exchange_id=ex)
