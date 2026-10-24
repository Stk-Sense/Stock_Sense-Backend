"""Strict causality and look-ahead bias prevention tests."""

import pandas as pd
from engine.backtest.event_driven import EventDrivenEngine
from engine.backtest.vectorized import VectorizedEngine
from engine.data.memory_feed import MemoryDataFeed
from engine.execution.fees import ZeroFeeModel
from engine.execution.simulator import ExecutionSimulator
from engine.execution.slippage import ZeroSlippage
from engine.models.candle import Bar
from engine.models.order import OrderType
from engine.strategy.base import Strategy


class CheatingStrategy(Strategy):
    """Attempts to peek at current bar's close and trade on the same bar."""

    def __init__(self) -> None:
        super().__init__()
        self.bars_seen = 0
        self.trade_timestamps = []

    def on_bar(self, bar: Bar) -> None:
        self.bars_seen += 1
        if self.bars_seen == 1:
            # Place buy order on first bar
            self.buy(symbol=bar.symbol, quantity=1.0, order_type=OrderType.MARKET)

    def on_trade(self, trade) -> None:
        self.trade_timestamps.append(trade.timestamp)


def test_event_driven_zero_lookahead():
    # 3 bars at timestamps 1000, 2000, 3000
    b1 = Bar(timestamp=1000, open=100.0, high=105.0, low=95.0, close=100.0, volume=10.0, symbol="BTC/USDT")
    b2 = Bar(timestamp=2000, open=102.0, high=108.0, low=101.0, close=107.0, volume=10.0, symbol="BTC/USDT")
    b3 = Bar(timestamp=3000, open=107.0, high=110.0, low=106.0, close=109.0, volume=10.0, symbol="BTC/USDT")

    feed = MemoryDataFeed([b1, b2, b3], symbol="BTC/USDT")
    strat = CheatingStrategy()
    sim = ExecutionSimulator(fee_model=ZeroFeeModel(), slippage_model=ZeroSlippage())
    engine = EventDrivenEngine(data_feed=feed, strategy=strat, simulator=sim)

    report = engine.run()

    # The order submitted on bar 1 (timestamp=1000) MUST execute at bar 2 (timestamp=2000), NEVER on bar 1!
    assert len(strat.trade_timestamps) == 1
    assert strat.trade_timestamps[0] == 2000  # Bar 2 timestamp!
    # The fill price MUST be Bar 2 Open (102.0), NOT Bar 1 Close (100.0)!
    assert report.trades[0]["price"] == 102.0


def test_vectorized_zero_lookahead():
    # Price rises from 100 to 200
    df = pd.DataFrame({
        "ts": [1000, 2000, 3000, 4000],
        "open": [100.0, 120.0, 150.0, 200.0],
        "high": [105.0, 125.0, 155.0, 205.0],
        "low": [95.0, 115.0, 145.0, 195.0],
        "close": [100.0, 120.0, 150.0, 200.0],
        "volume": [10.0, 10.0, 10.0, 10.0],
    })

    # Signal is 0 on bar 0, 1 on bar 1, 0 on bar 2, 0 on bar 3
    # If look-ahead existed: bar 1 return (from 100 to 120, +20%) would be captured.
    # Since look-ahead is prevented: signal from bar 1 takes effect on bar 2 (capturing return from 120 to 150, +25%).
    signals = [0.0, 1.0, 0.0, 0.0]

    engine = VectorizedEngine(fee_rate=0.0, slippage_bps=0.0, initial_cash=10_000.0)
    report = engine.run(df, signals)

    # Bar 1 (ts=2000): position=0.0, equity=10,000
    assert report.equity_curve[1]["equity"] == 10_000.0
    # Bar 2 (ts=3000): position=1.0, price went from 120 to 150 (+25%), equity=12,500
    assert report.equity_curve[2]["equity"] == 12_500.0
    # Bar 3 (ts=4000): position=0.0, equity stays 12,500
    assert report.equity_curve[3]["equity"] == 12_500.0
