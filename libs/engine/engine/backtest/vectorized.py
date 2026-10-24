"""Ultra-fast vectorized matrix backtesting engine for parameter sweeps."""

from typing import Any, Sequence, Union
import numpy as np
import pandas as pd

from engine.data.base import DataFeed
from engine.metrics.drawdown import calculate_drawdown_metrics
from engine.metrics.report import BacktestReport
from engine.metrics.returns import cagr_pct, total_return_pct
from engine.metrics.risk import (
    annualized_volatility_pct,
    calmar_ratio,
    sharpe_ratio,
    sortino_ratio,
)
from engine.metrics.trade_stats import calculate_trade_statistics


class VectorizedEngine:
    """Vectorized calculation engine evaluating signals against price series in milliseconds."""

    def __init__(
        self,
        fee_rate: float = 0.0004,       # 4 bps per trade
        slippage_bps: float = 2.0,      # 2 bps per trade
        initial_cash: float = 100_000.0,
        strategy_name: str = "VectorizedStrategy",
    ) -> None:
        self.fee_rate = fee_rate
        self.slippage_bps = slippage_bps
        self.initial_cash = initial_cash
        self.strategy_name = strategy_name

    def run(
        self,
        data: Union[DataFeed, pd.DataFrame],
        signals: Union[Sequence[float], pd.Series, np.ndarray],
    ) -> BacktestReport:
        """Run vectorized backtest on a price series and signal array.

        Args:
            data: DataFeed or DataFrame containing 'close' and 'ts'/'timestamp'.
            signals: Array/Series of target positions (1.0 for Long, -1.0 for Short, 0.0 for Flat).
        """
        if isinstance(data, DataFeed):
            df = data.to_dataframe()
            symbol = data.symbols[0]
            timeframe = data.timeframe
        else:
            df = data.copy()
            symbol = "UNKNOWN"
            timeframe = "1h"

        if len(df) == 0:
            raise ValueError("Data feed is empty")

        close_col = "close"
        ts_col = "ts" if "ts" in df.columns else "timestamp"

        close_series = df[close_col].astype(float)
        sig_series = pd.Series(signals, index=df.index).astype(float)

        # Zero look-ahead: Signal from bar t takes effect on bar t+1
        effective_position = sig_series.shift(1).fillna(0.0)

        # Bar percentage returns
        market_returns = close_series.pct_change().fillna(0.0)
        gross_strategy_returns = effective_position * market_returns

        # Friction cost on position changes
        position_changes = effective_position.diff().abs()
        position_changes.iloc[0] = abs(effective_position.iloc[0])

        total_friction_rate = self.fee_rate + (self.slippage_bps / 10_000.0)
        costs = position_changes * total_friction_rate

        net_returns = gross_strategy_returns - costs

        # Cumulative equity curve
        equity_series = self.initial_cash * (1.0 + net_returns).cumprod()

        start_ts = int(df[ts_col].iloc[0])
        end_ts = int(df[ts_col].iloc[-1])
        total_days = max(1.0, (end_ts - start_ts) / (1000.0 * 86400.0))

        tot_return = total_return_pct(self.initial_cash, float(equity_series.iloc[-1]))
        cagr = cagr_pct(self.initial_cash, float(equity_series.iloc[-1]), total_days)
        vol = annualized_volatility_pct(net_returns)
        sharpe = sharpe_ratio(net_returns)
        sortino = sortino_ratio(net_returns)
        max_dd, max_dd_dollar, max_dd_dur, underwater = calculate_drawdown_metrics(equity_series)
        calmar = calmar_ratio(cagr, max_dd)

        # Equity curve array (vectorized via numpy arrays)
        ts_arr = df[ts_col].to_numpy()
        eq_arr = equity_series.to_numpy()
        uw_arr = underwater.to_numpy()
        equity_records = [
            {
                "timestamp": int(t),
                "equity": round(float(e), 2),
                "drawdown_pct": round(float(abs(u)) * 100.0, 2),
            }
            for t, e, u in zip(ts_arr, eq_arr, uw_arr)
        ]

        return BacktestReport(
            strategy_name=self.strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            initial_cash=self.initial_cash,
            final_equity=float(equity_series.iloc[-1]),
            total_return_pct=tot_return,
            cagr_pct=cagr,
            annualized_volatility_pct=vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown_pct=max_dd,
            max_drawdown_duration_bars=max_dd_dur,
            trade_statistics=calculate_trade_statistics([]),  # Vectorized mode operates on continuous series
            total_bars=len(df),
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            equity_curve=equity_records,
            trades=[],
        )
