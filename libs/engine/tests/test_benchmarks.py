"""Performance and throughput benchmarks for backtest engine."""

import time
from conftest import generate_synthetic_bars
from engine.backtest.event_driven import EventDrivenEngine
from engine.backtest.vectorized import VectorizedEngine
from engine.data.memory_feed import MemoryDataFeed
from engine.models.candle import Bar
from engine.models.order import OrderType
from engine.strategy.base import Strategy


class BenchmarkStrategy(Strategy):
    """Simple strategy that flips positions periodically to stress-test execution."""

    def __init__(self, step: int = 10) -> None:
        super().__init__()
        self.step = step
        self.count = 0

    def on_bar(self, bar: Bar) -> None:
        self.count += 1
        if self.count % self.step == 0:
            pos = self.get_position(bar.symbol)
            if not pos.is_open:
                self.buy(symbol=bar.symbol, quantity=1.0, order_type=OrderType.MARKET)
            else:
                self.close_position(bar.symbol)


def test_event_driven_throughput_benchmark():
    # 20,000 synthetic bars
    bars = generate_synthetic_bars(count=20_000)
    feed = MemoryDataFeed(bars, symbol="BTC/USDT")
    strat = BenchmarkStrategy(step=10)
    engine = EventDrivenEngine(data_feed=feed, strategy=strat)

    start_time = time.perf_counter()
    report = engine.run()
    elapsed = time.perf_counter() - start_time

    bars_per_sec = len(bars) / elapsed
    print(f"\nEvent-Driven Throughput: {bars_per_sec:,.0f} bars/sec (processed {len(bars)} bars in {elapsed:.3f}s)")

    # Must process at least 15,000 bars/sec on standard CPU
    assert bars_per_sec >= 15_000, f"Throughput too low: {bars_per_sec:,.0f} bars/sec"
    assert report.total_bars == 20_000


def test_vectorized_throughput_benchmark():
    # 100,000 bars for vectorized test
    import numpy as np
    import pandas as pd

    count = 100_000
    df = pd.DataFrame({
        "ts": np.arange(count) * 60_000,
        "close": 50_000.0 + np.cumsum(np.random.randn(count) * 10.0),
    })
    signals = np.where(np.arange(count) % 20 < 10, 1.0, 0.0)

    engine = VectorizedEngine()

    start_time = time.perf_counter()
    report = engine.run(df, signals)
    elapsed = time.perf_counter() - start_time

    bars_per_sec = count / elapsed
    print(f"\nVectorized Throughput: {bars_per_sec:,.0f} bars/sec (processed {count} bars in {elapsed:.3f}s)")

    # Vectorized should achieve > 500,000 bars/sec
    assert bars_per_sec >= 200_000, f"Vectorized throughput too low: {bars_per_sec:,.0f} bars/sec"
    assert report.total_bars == count
