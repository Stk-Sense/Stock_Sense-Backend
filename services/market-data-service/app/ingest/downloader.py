"""Downloader engine with pagination and forming-candle exclusion."""

import time
from typing import Generator, Optional, Union
from app.exchange.base import ExchangeClient
from app.ingest.timeframes import tf_to_ms
from common.logging import get_logger

logger = get_logger("downloader")


class Downloader:
    """Orchestrates historical OHLCV pagination from an ExchangeClient."""

    def __init__(self, exchange_client: ExchangeClient) -> None:
        self.exchange = exchange_client

    def fetch_batches(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: Optional[int] = None,
        batch_limit: int = 1000,
        current_time_ms: Optional[int] = None,
    ) -> Generator[list[list[Union[int, float]]], None, None]:
        """Fetch candle batches iteratively.

        Only returns fully closed candles:
            candle[0] + tf_ms <= now_ms
        If end_ts is provided, only includes candles where candle[0] < end_ts.

        Yields:
            Batches of closed candles.
        """
        tf_ms = tf_to_ms(timeframe)
        now_ms = current_time_ms if current_time_ms is not None else int(time.time() * 1000)
        cursor = start_ts

        logger.info(
            f"Starting download for {symbol} {timeframe} from ts={start_ts} to end_ts={end_ts}",
            extra={"symbol": symbol, "timeframe": timeframe, "start_ts": start_ts, "end_ts": end_ts},
        )

        while True:
            # Stop if cursor already passes current time or requested end_ts
            if cursor + tf_ms > now_ms:
                logger.info(f"Cursor ({cursor}) reached now boundary ({now_ms}). Stopping.")
                break

            if end_ts is not None and cursor >= end_ts:
                logger.info(f"Cursor ({cursor}) reached requested end_ts ({end_ts}). Stopping.")
                break

            raw_candles = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=cursor,
                limit=batch_limit,
            )

            if not raw_candles:
                logger.info(f"No more candles returned by exchange at cursor {cursor}. Stopping.")
                break

            # Filter forming candle: keep ONLY candles where ts + tf_ms <= now_ms
            # and if end_ts is specified, ts < end_ts
            closed_candles = []
            for c in raw_candles:
                candle_ts = int(c[0])
                if candle_ts + tf_ms > now_ms:
                    # Still forming / incomplete candle: drop it!
                    logger.debug(f"Dropping still-forming candle at ts={candle_ts} (now={now_ms})")
                    continue
                if end_ts is not None and candle_ts >= end_ts:
                    continue
                closed_candles.append(c)

            if not closed_candles:
                # All candles in this batch were forming or beyond end_ts
                logger.info("Batch contained only forming or out-of-range candles. Stopping.")
                break

            yield closed_candles

            # Advance cursor past the last returned raw candle
            last_candle_ts = int(raw_candles[-1][0])
            next_cursor = last_candle_ts + tf_ms

            if next_cursor <= cursor:
                # Prevent infinite loop if exchange repeatedly returns older/identical timestamp
                logger.warning(
                    f"Exchange returned non-advancing candle ts {last_candle_ts} vs cursor {cursor}. Forcing forward."
                )
                cursor = cursor + (batch_limit * tf_ms)
            else:
                cursor = next_cursor

            # If exchange returned fewer than requested limit, we have reached the latest available data
            if len(raw_candles) < batch_limit:
                logger.info(f"Received partial batch ({len(raw_candles)} < {batch_limit}). Reached tip.")
                break
