"""Unit tests for VectorizedEngine."""

import numpy as np
import pandas as pd
import pytest
from engine.backtest.vectorized import VectorizedEngine


def test_vectorized_engine_crossover():
    prices = [100.0, 102.0, 105.0, 103.0, 107.0, 110.0, 108.0, 112.0]
    df = pd.DataFrame({
        "ts": [1000 * (i + 1) for i in range(len(prices))],
        "close": prices,
    })

    # Signal: buy at index 1, sell at index 5
    signals = [0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0]

    engine = VectorizedEngine(fee_rate=0.0005, slippage_bps=1.0, initial_cash=100_000.0)
    report = engine.run(df, signals)

    assert report.total_bars == len(prices)
    assert len(report.equity_curve) == len(prices)
    assert report.final_equity > report.initial_cash  # Profitable Long trade
    assert report.max_drawdown_pct >= 0.0


def test_vectorized_empty_data():
    df_empty = pd.DataFrame(columns=["ts", "close"])
    engine = VectorizedEngine()
    with pytest.raises(ValueError):
        engine.run(df_empty, [])
