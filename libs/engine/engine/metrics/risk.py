"""Risk and risk-adjusted return ratio calculations."""

import numpy as np
import pandas as pd


def annualized_volatility_pct(returns: pd.Series, periods_per_year: float = 365.25 * 24) -> float:
    """Calculate annualized standard deviation of returns in percentage."""
    if len(returns) < 2:
        return 0.0
    vol = returns.std(ddof=1) * np.sqrt(periods_per_year)
    return float(vol * 100.0) if not np.isnan(vol) else 0.0


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: float = 365.25 * 24,
) -> float:
    """Calculate the annualized Sharpe Ratio.

    Args:
        returns: Fractional return series per bar.
        risk_free_rate: Annualized risk-free interest rate (e.g. 0.02 for 2%).
        periods_per_year: Number of periods in a year.
    """
    if len(returns) < 2:
        return 0.0
    rf_per_period = risk_free_rate / periods_per_year
    excess_returns = returns - rf_per_period
    std = excess_returns.std(ddof=1)
    if std <= 1e-9 or np.isnan(std):
        return 0.0
    sharpe = (excess_returns.mean() / std) * np.sqrt(periods_per_year)
    return float(sharpe) if not np.isnan(sharpe) else 0.0


def sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: float = 365.25 * 24,
) -> float:
    """Calculate the annualized Sortino Ratio focusing on downside risk."""
    if len(returns) < 2:
        return 0.0
    rf_per_period = risk_free_rate / periods_per_year
    excess_returns = returns - rf_per_period
    downside_returns = excess_returns[excess_returns < 0.0]

    if len(downside_returns) == 0:
        return float("inf") if excess_returns.mean() > 0 else 0.0

    downside_std = np.sqrt(np.mean(downside_returns ** 2))
    if downside_std <= 1e-9 or np.isnan(downside_std):
        return 0.0

    sortino = (excess_returns.mean() / downside_std) * np.sqrt(periods_per_year)
    return float(sortino) if not np.isnan(sortino) else 0.0


def calmar_ratio(annualized_return_pct: float, max_drawdown_pct: float) -> float:
    """Calculate the Calmar Ratio (Annualized Return / Max Drawdown)."""
    if max_drawdown_pct <= 1e-9:
        return float("inf") if annualized_return_pct > 0 else 0.0
    return float(annualized_return_pct / max_drawdown_pct)
