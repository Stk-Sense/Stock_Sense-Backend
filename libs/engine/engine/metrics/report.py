"""Aggregated backtest report and serialization."""

import json
from dataclasses import asdict, dataclass
from typing import Any, Optional
import pandas as pd


@dataclass
class BacktestReport:
    """Complete institutional performance report of a backtest run."""

    strategy_name: str
    symbol: str
    timeframe: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    annualized_volatility_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_duration_bars: int
    trade_statistics: dict[str, Any]
    total_bars: int
    start_timestamp: int
    end_timestamp: int
    equity_curve: list[dict[str, Any]]
    trades: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return {
            "summary": {
                "strategy_name": self.strategy_name,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "initial_cash": round(self.initial_cash, 2),
                "final_equity": round(self.final_equity, 2),
                "total_return_pct": round(self.total_return_pct, 2),
                "cagr_pct": round(self.cagr_pct, 2),
                "annualized_volatility_pct": round(self.annualized_volatility_pct, 2),
                "sharpe_ratio": round(self.sharpe_ratio, 2),
                "sortino_ratio": round(self.sortino_ratio, 2),
                "calmar_ratio": round(self.calmar_ratio, 2),
                "max_drawdown_pct": round(self.max_drawdown_pct, 2),
                "max_drawdown_duration_bars": self.max_drawdown_duration_bars,
                "total_bars": self.total_bars,
                "start_timestamp": self.start_timestamp,
                "end_timestamp": self.end_timestamp,
            },
            "trade_statistics": self.trade_statistics,
            "equity_curve": self.equity_curve,
            "trades": self.trades,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def equity_dataframe(self) -> pd.DataFrame:
        """Return the equity curve time-series as a Pandas DataFrame."""
        return pd.DataFrame(self.equity_curve)

    def trades_dataframe(self) -> pd.DataFrame:
        """Return the trade log as a Pandas DataFrame."""
        return pd.DataFrame(self.trades)
