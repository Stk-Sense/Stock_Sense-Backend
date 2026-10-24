"""Drawdown analysis and underwater series calculation."""

from typing import Tuple
import pandas as pd


def calculate_drawdown_metrics(equity_series: pd.Series) -> Tuple[float, float, int, pd.Series]:
    """Calculate maximum drawdown percentage, dollar drop, max duration, and underwater series.

    Returns:
        (max_dd_pct, max_dd_dollar, max_duration_bars, underwater_series)
    """
    if len(equity_series) == 0:
        return 0.0, 0.0, 0, pd.Series(dtype=float)

    hwm = equity_series.cummax()
    dollar_dd = hwm - equity_series
    underwater = -dollar_dd / hwm

    max_dd_pct = float(abs(underwater.min())) * 100.0 if not underwater.empty else 0.0
    max_dd_dollar = float(dollar_dd.max()) if not dollar_dd.empty else 0.0

    # Calculate maximum drawdown duration (consecutive bars where equity < hwm)
    is_in_dd = (equity_series < hwm).to_numpy()
    max_duration = 0
    current_duration = 0

    for in_dd in is_in_dd:
        if in_dd:
            current_duration += 1
            if current_duration > max_duration:
                max_duration = current_duration
        else:
            current_duration = 0

    return max_dd_pct, max_dd_dollar, max_duration, underwater
