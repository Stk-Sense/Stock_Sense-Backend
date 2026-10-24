"""Unit tests for fee and slippage models."""

from engine.execution.fees import FixedFeeModel, MakerTakerFeeModel
from engine.execution.slippage import FixedBpsSlippage, VolatilitySlippage
from engine.models.candle import Bar
from engine.models.order import Order, OrderSide, OrderType


def test_maker_taker_fee_model():
    model = MakerTakerFeeModel(maker_fee_rate=0.0002, taker_fee_rate=0.0004)
    order = Order(symbol="BTC/USDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=2.0)

    # Taker fee on 2 BTC @ $50,000 = $100,000 * 0.0004 = $40.00
    fee_taker = model.calculate_fee(order, fill_price=50_000.0, fill_qty=2.0, is_maker=False)
    assert round(fee_taker, 2) == 40.0

    # Maker fee on 2 BTC @ $50,000 = $100,000 * 0.0002 = $20.00
    fee_maker = model.calculate_fee(order, fill_price=50_000.0, fill_qty=2.0, is_maker=True)
    assert round(fee_maker, 2) == 20.0


def test_fixed_fee_model():
    model = FixedFeeModel(fee_per_trade=5.0)
    order = Order(symbol="ETH/USDT", side=OrderSide.SELL, type=OrderType.MARKET, quantity=10.0)
    fee = model.calculate_fee(order, fill_price=3000.0, fill_qty=10.0)
    assert fee == 5.0


def test_fixed_bps_slippage():
    # 10 bps = 0.10%
    model = FixedBpsSlippage(bps=10.0)
    bar = Bar(timestamp=1704067200000, open=100.0, high=105.0, low=95.0, close=100.0, volume=100.0)

    # Buy: price penalized upwards (+0.10%) -> 100.10
    buy_order = Order(symbol="BTC/USDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=1.0)
    buy_slipped = model.calculate_slippage(buy_order, bar, expected_price=100.0)
    assert round(buy_slipped, 2) == 100.10

    # Sell: price penalized downwards (-0.10%) -> 99.90
    sell_order = Order(symbol="BTC/USDT", side=OrderSide.SELL, type=OrderType.MARKET, quantity=1.0)
    sell_slipped = model.calculate_slippage(sell_order, bar, expected_price=100.0)
    assert round(sell_slipped, 2) == 99.90


def test_volatility_slippage():
    # Bar range = 110 - 90 = 20.0. Range fraction 5% = $1.00 slippage penalty
    model = VolatilitySlippage(range_fraction=0.05)
    bar = Bar(timestamp=1704067200000, open=100.0, high=110.0, low=90.0, close=105.0, volume=50.0)

    buy_order = Order(symbol="BTC/USDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=1.0)
    buy_price = model.calculate_slippage(buy_order, bar, expected_price=100.0)
    assert buy_price == 101.0

    sell_order = Order(symbol="BTC/USDT", side=OrderSide.SELL, type=OrderType.MARKET, quantity=1.0)
    sell_price = model.calculate_slippage(sell_order, bar, expected_price=100.0)
    assert sell_price == 99.0
