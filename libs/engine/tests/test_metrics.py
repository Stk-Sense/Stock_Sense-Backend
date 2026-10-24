"""Unit tests for quantitative risk and performance metric formulas."""

import numpy as np
import pandas as pd
from engine.metrics.drawdown import calculate_drawdown_metrics
from engine.metrics.returns import cagr_pct, total_return_pct
from engine.metrics.risk import (
    annualized_volatility_pct,
    calmar_ratio,
    sharpe_ratio,
    sortino_ratio,
)
from engine.metrics.trade_stats import calculate_trade_statistics
from engine.models.order import OrderSide
from engine.models.trade import Trade


def test_total_return_and_cagr():
    assert total_return_pct(100.0, 150.0) == 50.0
    assert total_return_pct(100.0, 80.0) == -20.0

    # Doubled in exactly 1 year (365.25 days) -> 100% CAGR
    assert round(cagr_pct(100.0, 200.0, 365.25), 1) == 100.0


def test_drawdown_calculation():
    # Peak at 100, drops to 80 (20% drawdown), recovers to 110
    equity = pd.Series([100.0, 100.0, 90.0, 80.0, 85.0, 110.0])
    max_dd, max_dd_dollar, max_dur, underwater = calculate_drawdown_metrics(equity)

    assert max_dd == 20.0
    assert max_dd_dollar == 20.0
    assert max_dur == 3  # bars at index 2, 3, 4 were below 100


def test_sharpe_and_sortino_ratios():
    # Constant 1% positive return series with low noise
    returns = pd.Series([0.01, 0.012, 0.009, 0.011, 0.010, 0.013])
    sharpe = sharpe_ratio(returns, risk_free_rate=0.0)
    assert sharpe > 0.0

    # Sortino ratio: with zero negative returns, Sortino is positive infinity
    sortino = sortino_ratio(returns, risk_free_rate=0.0)
    assert sortino == float("inf")

    # Introducing negative returns
    returns_with_loss = pd.Series([0.01, -0.02, 0.015, -0.01, 0.02])
    sortino_loss = sortino_ratio(returns_with_loss, risk_free_rate=0.0)
    assert sortino_loss > 0.0


def test_calmar_ratio():
    assert calmar_ratio(annualized_return_pct=30.0, max_drawdown_pct=15.0) == 2.0
    assert calmar_ratio(annualized_return_pct=20.0, max_drawdown_pct=0.0) == float("inf")


def test_trade_statistics():
    trades = [
        Trade(order_id="1", symbol="BTC/USDT", side=OrderSide.BUY, quantity=1.0, price=100.0, fee=1.0, timestamp=1000, realized_pnl=0.0),
        Trade(order_id="2", symbol="BTC/USDT", side=OrderSide.SELL, quantity=1.0, price=150.0, fee=1.0, timestamp=2000, realized_pnl=50.0),   # Win +50
        Trade(order_id="3", symbol="BTC/USDT", side=OrderSide.BUY, quantity=1.0, price=150.0, fee=1.0, timestamp=3000, realized_pnl=0.0),
        Trade(order_id="4", symbol="BTC/USDT", side=OrderSide.SELL, quantity=1.0, price=130.0, fee=1.0, timestamp=4000, realized_pnl=-20.0), # Loss -20
    ]

    stats = calculate_trade_statistics(trades)
    assert stats["total_trades"] == 4
    assert stats["closed_trades"] == 2
    assert stats["winning_trades"] == 1
    assert stats["losing_trades"] == 1
    assert stats["win_rate_pct"] == 50.0
    assert stats["gross_profit"] == 50.0
    assert stats["gross_loss"] == 20.0
    assert stats["profit_factor"] == 2.5
    assert stats["average_win"] == 50.0
    assert stats["average_loss"] == 20.0
    assert stats["payoff_ratio"] == 2.5
    # Expectancy = (0.5 * 50) - (0.5 * 20) = 25 - 10 = 15.0
    assert stats["expectancy"] == 15.0
