"""Unit tests for engine domain models (Order, Position, Account)."""

import pytest
from engine.models.account import Account
from engine.models.candle import Bar
from engine.models.order import Order, OrderSide, OrderStatus, OrderType
from engine.models.position import Position, PositionSide


def test_bar_creation():
    bar = Bar(timestamp=1704067200000, open=100.0, high=105.0, low=95.0, close=102.0, volume=10.0)
    assert bar.open == 100.0
    assert bar.high == 105.0
    assert bar.symbol == "UNKNOWN"

    from_row = Bar.from_row([1704067200000, 100.0, 105.0, 95.0, 102.0, 10.0], symbol="BTC/USDT")
    assert from_row.symbol == "BTC/USDT"


def test_order_creation_and_fill():
    order = Order(symbol="BTC/USDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=2.0)
    assert order.is_active is True
    assert order.status == OrderStatus.PENDING

    # Partial fill
    order.fill(fill_qty=1.0, fill_price=50000.0, fee=20.0, timestamp=1704067200000)
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == 1.0
    assert order.filled_avg_price == 50000.0

    # Final fill
    order.fill(fill_qty=1.0, fill_price=51000.0, fee=20.4, timestamp=1704067260000)
    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 2.0
    assert order.filled_avg_price == 50500.0
    assert order.is_active is False


def test_position_long_accounting():
    pos = Position(symbol="BTC/USDT")
    assert pos.side == PositionSide.FLAT

    # Open Long 1.0 @ 50,000
    pnl1 = pos.apply_fill(OrderSide.BUY, fill_qty=1.0, fill_price=50_000.0)
    assert pnl1 == 0.0
    assert pos.side == PositionSide.LONG
    assert pos.quantity == 1.0
    assert pos.entry_price == 50_000.0

    # Mark-to-market at 55,000
    pos.update_market_price(55_000.0)
    assert pos.unrealized_pnl == 5_000.0
    assert pos.unrealized_pnl_pct == 0.10

    # Partial close 0.5 @ 54,000
    pnl2 = pos.apply_fill(OrderSide.SELL, fill_qty=0.5, fill_price=54_000.0)
    assert pnl2 == 2_000.0  # (54000 - 50000) * 0.5
    assert pos.quantity == 0.5
    assert pos.entry_price == 50_000.0  # Entry price unchanged on partial close

    # Flip to Short 1.0 @ 48,000 (selling 1.5 units)
    pnl3 = pos.apply_fill(OrderSide.SELL, fill_qty=1.5, fill_price=48_000.0)
    assert pnl3 == -1_000.0  # (48000 - 50000) * 0.5
    assert pos.side == PositionSide.SHORT
    assert pos.quantity == -1.0
    assert pos.entry_price == 48_000.0


def test_account_spot_and_futures_mode():
    # Spot Account
    spot_acc = Account(initial_cash=100_000.0, is_futures_mode=False)
    assert spot_acc.equity == 100_000.0

    # Buy 1 BTC @ 50,000 with $20 fee
    trade1 = spot_acc.process_fill(
        order_id="test-1",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=1.0,
        price=50_000.0,
        fee=20.0,
        timestamp=1704067200000,
    )
    # Cash spent = 50,000 + 20 fee = 50,020. Remaining cash = 49,980
    assert spot_acc.cash == 49_980.0
    assert spot_acc.equity == 99_980.0  # 49,980 cash + 50,000 asset value

    # Price moves to 60,000
    spot_acc.update_prices({"BTC/USDT": 60_000.0})
    assert spot_acc.equity == 109_980.0  # 49,980 + 60,000

    # Futures Account
    fut_acc = Account(initial_cash=100_000.0, is_futures_mode=True, default_leverage=5.0)
    fut_acc.process_fill(
        order_id="test-2",
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        quantity=1.0,
        price=50_000.0,
        fee=20.0,
        timestamp=1704067200000,
    )
    # Cash only reduced by fee
    assert fut_acc.cash == 99_980.0
    # Margin used = 50,000 / 5x = 10,000
    assert fut_acc.total_margin_used == 10_000.0
    assert fut_acc.free_margin == 89_980.0
