"""Shared fixtures for backtesting engine test suite."""

import pytest
from engine.models.candle import Bar


def generate_synthetic_bars(
    count: int = 100,
    start_ts: int = 1704067200000,
    base_price: float = 50_000.0,
    timeframe_ms: int = 3600000,
    symbol: str = "BTC/USDT",
) -> list[Bar]:
    """Generate deterministic synthetic bars for unit tests."""
    bars: list[Bar] = []
    curr_price = base_price

    for i in range(count):
        ts = start_ts + (i * timeframe_ms)
        # Gentle cyclical pattern
        delta = 20.0 if (i % 4) in (0, 1) else -15.0
        open_p = curr_price
        close_p = open_p + delta
        high_p = max(open_p, close_p) + 10.0
        low_p = min(open_p, close_p) - 10.0
        vol = 100.0 + (i % 10) * 5.0

        bars.append(
            Bar(
                timestamp=ts,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=vol,
                symbol=symbol,
            )
        )
        curr_price = close_p

    return bars


@pytest.fixture
def synthetic_bars():
    return generate_synthetic_bars(count=100)
