"""Integration tests for EventDrivenEngine simulation."""

from engine.backtest.event_driven import EventDrivenEngine
from engine.data.memory_feed import MemoryDataFeed
from engine.execution.fees import MakerTakerFeeModel
from engine.execution.simulator import ExecutionSimulator
from engine.execution.slippage import FixedBpsSlippage
from engine.models.account import Account
from engine.models.candle import Bar
from engine.models.order import OrderType
from engine.strategy.base import Strategy


class SMACrossoverStrategy(Strategy):
    """Simple moving average crossover strategy."""

    def __init__(self, fast_window: int = 3, slow_window: int = 6) -> None:
        super().__init__()
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.prices: list[float] = []

    def on_bar(self, bar: Bar) -> None:
        self.prices.append(bar.close)
        if len(self.prices) < self.slow_window:
            return

        fast_sma = sum(self.prices[-self.fast_window:]) / self.fast_window
        slow_sma = sum(self.prices[-self.slow_window:]) / self.slow_window

        pos = self.get_position(bar.symbol)
        if fast_sma > slow_sma and not pos.is_open:
            self.buy(symbol=bar.symbol, quantity=1.0, order_type=OrderType.MARKET)
        elif fast_sma < slow_sma and pos.is_open:
            self.close_position(bar.symbol)


def test_event_driven_sma_strategy(synthetic_bars):
    feed = MemoryDataFeed(synthetic_bars, symbol="BTC/USDT")
    strat = SMACrossoverStrategy(fast_window=3, slow_window=6)
    sim = ExecutionSimulator(
        fee_model=MakerTakerFeeModel(maker_fee_rate=0.0002, taker_fee_rate=0.0004),
        slippage_model=FixedBpsSlippage(bps=2.0),
    )
    acc = Account(initial_cash=100_000.0, is_futures_mode=False)
    engine = EventDrivenEngine(data_feed=feed, strategy=strat, account=acc, simulator=sim)

    report = engine.run()

    assert report.total_bars == len(synthetic_bars)
    assert len(report.equity_curve) == len(synthetic_bars)
    assert report.initial_cash == 100_000.0
    assert report.trade_statistics["total_trades"] > 0
    assert "summary" in report.to_dict()
    assert len(report.to_json()) > 0


def test_event_driven_margin_call_liquidation():
    # Price crashes by 90%
    bars = [
        Bar(timestamp=1000, open=100.0, high=105.0, low=95.0, close=100.0, volume=10.0, symbol="BTC/USDT"),
        Bar(timestamp=2000, open=100.0, high=102.0, low=98.0, close=100.0, volume=10.0, symbol="BTC/USDT"),
        Bar(timestamp=3000, open=20.0, high=25.0, low=15.0, close=20.0, volume=10.0, symbol="BTC/USDT"),
    ]
    feed = MemoryDataFeed(bars, symbol="BTC/USDT")

    class HighLeverageStrategy(Strategy):
        def on_bar(self, bar: Bar) -> None:
            if bar.timestamp == 1000:
                # Buy 500 units @ $100 = $50,000 notional on $10,000 account (5x leverage)
                self.buy(symbol=bar.symbol, quantity=500.0, order_type=OrderType.MARKET)

    acc = Account(initial_cash=10_000.0, is_futures_mode=True, default_leverage=5.0)
    engine = EventDrivenEngine(data_feed=feed, strategy=HighLeverageStrategy(), account=acc)

    report = engine.run()

    # The crash on bar 3 causes equity to fall below maintenance margin, triggering liquidation
    assert acc.is_liquidatable or acc.positions["BTC/USDT"].quantity == 0.0
    # Position was liquidated
    assert acc.positions["BTC/USDT"].quantity == 0.0
