"""CCXT-based ExchangeClient implementation with exponential backoff and rate limiting."""

import random
import time
from typing import Optional, Union
import ccxt

from app.exchange.base import ExchangeClient
from common.logging import get_logger

logger = get_logger("ccxt_client")


class CCXTExchangeClient(ExchangeClient):
    """CCXT client wrapper with rate limiting and exponential backoff."""

    def __init__(
        self,
        exchange_id: str = "binance",
        max_retries: int = 5,
        base_backoff_sec: float = 1.0,
        max_backoff_sec: float = 30.0,
    ) -> None:
        self._exchange_id = exchange_id.lower()
        self._max_retries = max_retries
        self._base_backoff_sec = base_backoff_sec
        self._max_backoff_sec = max_backoff_sec

        exchange_class = getattr(ccxt, self._exchange_id, None)
        if not exchange_class:
            raise ValueError(f"Exchange '{exchange_id}' is not supported by ccxt.")

        self._client: ccxt.Exchange = exchange_class({
            "enableRateLimit": True,
            "timeout": 30000,
        })

    @property
    def exchange_id(self) -> str:
        return self._exchange_id

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[list[Union[int, float]]]:
        """Fetch candles with retry loop and exponential backoff."""
        attempt = 0
        while True:
            try:
                data = self._client.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
                return data or []
            except (ccxt.RateLimitExceeded, ccxt.NetworkError, ccxt.RequestTimeout) as exc:
                attempt += 1
                if attempt > self._max_retries:
                    logger.error(
                        f"Max retries ({self._max_retries}) exceeded fetching OHLCV for {symbol} {timeframe}: {exc}",
                        extra={"symbol": symbol, "timeframe": timeframe, "since": since, "attempt": attempt},
                    )
                    raise

                sleep_time = min(self._max_backoff_sec, self._base_backoff_sec * (2 ** (attempt - 1)))
                jitter = random.uniform(0.1, 0.5)
                wait_duration = sleep_time + jitter

                logger.warning(
                    f"Exchange error ({type(exc).__name__}). Retrying {attempt}/{self._max_retries} in {wait_duration:.2f}s: {exc}",
                    extra={"symbol": symbol, "timeframe": timeframe, "since": since, "attempt": attempt},
                )
                time.sleep(wait_duration)
            except Exception as exc:
                logger.error(
                    f"Fatal unrecoverable error fetching OHLCV for {symbol} {timeframe}: {exc}",
                    extra={"symbol": symbol, "timeframe": timeframe, "since": since},
                )
                raise

    def fetch_markets(self) -> list[str]:
        """Fetch active market symbol names."""
        try:
            markets = self._client.load_markets()
            return list(markets.keys())
        except Exception as exc:
            logger.error(f"Failed to load markets for {self._exchange_id}: {exc}")
            raise

    def close(self) -> None:
        if hasattr(self._client, "close"):
            self._client.close()
