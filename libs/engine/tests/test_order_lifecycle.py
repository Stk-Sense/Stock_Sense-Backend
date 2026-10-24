"""Unit tests for realistic order matching and lifecycle simulation."""

from engine.execution.fees import ZeroFeeModel
from engine.execution.simulator import ExecutionSimulator
from engine.execution.slippage import ZeroSlippage
from engine.models.candle import Bar
from engine.models.order import Order, OrderSide, OrderType


def test_market_order_fill():
    sim = ExecutionSimulator(fee_model=ZeroFeeModel(), slippage_model=ZeroSlippage())
    bar = Bar(timestamp=1704067200000, open=50_000.0, high=50_500.0, low=49_800.0, close=50_200.0, volume=10.0)
    order = Order(symbol="BTC/USDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=1.0)

    res = sim.evaluate_order(order, bar)
    assert res.filled is True
    assert res.fill_price == 50_000.0  # Fills at bar open


def test_limit_buy_penetration_and_price_improvement():
    sim = ExecutionSimulator(fee_model=ZeroFeeModel(), slippage_model=ZeroSlippage())

    # Case A: Low penetrates limit price (Open=50,200, Low=49,800, Limit=50,000)
    bar1 = Bar(timestamp=1704067200000, open=50_200.0, high=50_500.0, low=49_800.0, close=50_100.0, volume=10.0)
    order1 = Order(symbol="BTC/USDT", side=OrderSide.BUY, type=OrderType.LIMIT, quantity=1.0, limit_price=50_000.0)
    res1 = sim.evaluate_order(order1, bar1)
    assert res1.filled is True
    assert res1.fill_price == 50_000.0

    # Case B: Price improvement! Market opens below limit (Open=49,500, Limit=50,000)
    bar2 = Bar(timestamp=1704067200000, open=49_500.0, high=50_500.0, low=49_000.0, close=50_100.0, volume=10.0)
    order2 = Order(symbol="BTC/USDT", side=OrderSide.BUY, type=OrderType.LIMIT, quantity=1.0, limit_price=50_000.0)
    res2 = sim.evaluate_order(order2, bar2)
    assert res2.filled is True
    assert res2.fill_price == 49_500.0  # Fills at Open (better price!)

    # Case C: Not filled (Low stayed above limit)
    bar3 = Bar(timestamp=1704067200000, open=51_000.0, high=51_500.0, low=50_500.0, close=51_200.0, volume=10.0)
    order3 = Order(symbol="BTC/USDT", side=OrderSide.BUY, type=OrderType.LIMIT, quantity=1.0, limit_price=50_000.0)
    res3 = sim.evaluate_order(order3, bar3)
    assert res3.filled is False


def test_stop_loss_gapping():
    sim = ExecutionSimulator(fee_model=ZeroFeeModel(), slippage_model=ZeroSlippage())

    # Stop Loss at 49,000. Market GAPS DOWN and opens at 48,000!
    # A realistic engine must fill at 48,000 (Open), NOT at fictional 49,000!
    bar_gap = Bar(timestamp=1704067200000, open=48_000.0, high=48_200.0, low=47_500.0, close=47_800.0, volume=10.0)
    order_sl = Order(symbol="BTC/USDT", side=OrderSide.SELL, type=OrderType.STOP_LOSS, quantity=1.0, stop_price=49_000.0)

    res = sim.evaluate_order(order_sl, bar_gap)
    assert res.filled is True
    assert res.fill_price == 48_000.0  # Realistic gap-down fill


def test_trailing_stop_dynamic_peak():
    sim = ExecutionSimulator(fee_model=ZeroFeeModel(), slippage_model=ZeroSlippage())
    # Trailing stop 10% below peak
    order = Order(
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        type=OrderType.TRAILING_STOP,
        quantity=1.0,
        trailing_delta=0.10,
    )

    # Bar 1: Peak rises to 100,000. Dynamic stop = 90,000. Low = 95,000 (no fill)
    bar1 = Bar(timestamp=1704067200000, open=92_000.0, high=100_000.0, low=95_000.0, close=98_000.0, volume=1.0)
    res1 = sim.evaluate_order(order, bar1)
    assert res1.filled is False
    assert order.high_water_mark == 100_000.0

    # Bar 2: Drops to Low 88,000 (triggers stop at 90,000)
    bar2 = Bar(timestamp=1704067260000, open=96_000.0, high=97_000.0, low=88_000.0, close=89_000.0, volume=1.0)
    res2 = sim.evaluate_order(order, bar2)
    assert res2.filled is True
    assert res2.fill_price == 90_000.0
