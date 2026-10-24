"""Return calculations for backtesting performance."""

import numpy as np
import pandas as pd


def total_return_pct(initial_equity: float, final_equity: float) -> float:
    """Calculate total percentage return."""
    if initial_equity <= 0:
        return 0.0
    return ((final_equity - initial_equity) / initial_equity) * 100.0


def cagr_pct(initial_equity: float, final_equity: float, total_days: float) -> float:
    """Calculate Compound Annual Growth Rate (CAGR) in percentage."""
    if initial_equity <= 0 or final_equity <= 0 or total_days <= 0:
        return 0.0
    years = total_days / 365.25
    cagr_value = (final_equity / initial_equity) ** (1.0 / years) - 1.0
    return cagr_value * 100.0


def period_returns(equity_series: pd.Series) -> pd.Series:
    """Calculate fractional percentage returns per step."""
    return equity_series.pct_change().fillna(0.0)
