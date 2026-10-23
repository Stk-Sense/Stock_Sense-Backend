"""Deterministic FakeExchangeClient for fast unit and integration tests."""

from typing import Optional, Union
from app.exchange.base import ExchangeClient
from app.ingest.timeframes import tf_to_ms


class FakeExchangeClient(ExchangeClient):
    """In-memory mock exchange for deterministic testing without network calls."""

    def __init__(self, exchange_id: str = "fake_binance") -> None:
        self._exchange_id = exchange_id
        # Mapping: (symbol, timeframe) -> sorted list of [ts, o, h, l, c, v]
        self._data: dict[tuple[str, str], list[list[Union[int, float]]]] = {}
        self._error_trigger_count = 0
        self._error_to_raise: Optional[Exception] = None

    @property
    def exchange_id(self) -> str:
        return self._exchange_id

    def set_candles(self, symbol: str, timeframe: str, candles: list[list[Union[int, float]]]) -> None:
        """Seed candle data for a given symbol and timeframe."""
        sorted_candles = sorted(candles, key=lambda c: c[0])
        self._data[(symbol, timeframe)] = sorted_candles

    def generate_synthetic_candles(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        count: int,
        base_price: float = 50000.0,
    ) -> list[list[Union[int, float]]]:
        """Generate a series of continuous synthetic candles."""
        tf_ms = tf_to_ms(timeframe)
        candles: list[list[Union[int, float]]] = []
        curr_price = base_price

        for i in range(count):
            ts = start_ts + (i * tf_ms)
            o = curr_price
            h = curr_price + 25.0
            l = curr_price - 25.0
            c = curr_price + 10.0
            v = 1.5 + (i % 5) * 0.2
            candles.append([ts, o, h, l, c, v])
            curr_price = c

        self._data[(symbol, timeframe)] = candles
        return candles

    def set_transient_error(self, error: Exception, trigger_count: int = 1) -> None:
        """Simulate errors for next N fetch calls."""
        self._error_to_raise = error
        self._error_trigger_count = trigger_count

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[list[Union[int, float]]]:
        if self._error_trigger_count > 0 and self._error_to_raise:
            self._error_trigger_count -= 1
            raise self._error_to_raise

        all_candles = self._data.get((symbol, timeframe), [])
        if since is not None:
            filtered = [c for c in all_candles if c[0] >= since]
        else:
            filtered = all_candles

        max_limit = limit if limit is not None else 1000
        return filtered[:max_limit]

    def fetch_markets(self) -> list[str]:
        symbols = {k[0] for k in self._data.keys()}
        return list(symbols) if symbols else ["BTC/USDT", "ETH/USDT"]

    def close(self) -> None:
        pass
