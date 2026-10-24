"""StockSense Backtest Engine Library Public API."""

from engine.models.candle import Bar
from engine.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)
from engine.models.trade import Trade
from engine.models.position import Position, PositionSide
from engine.models.account import Account

from engine.data.base import DataFeed
from engine.data.parquet_feed import ParquetDataFeed
from engine.data.memory_feed import MemoryDataFeed

from engine.execution.base import FeeModel, FillResult, SlippageModel
from engine.execution.fees import FixedFeeModel, MakerTakerFeeModel, ZeroFeeModel
from engine.execution.slippage import FixedBpsSlippage, VolatilitySlippage, ZeroSlippage
from engine.execution.simulator import ExecutionSimulator

from engine.strategy.base import Strategy

from engine.backtest.event_driven import EventDrivenEngine
from engine.backtest.vectorized import VectorizedEngine

from engine.metrics.report import BacktestReport
from engine.metrics.returns import cagr_pct, total_return_pct
from engine.metrics.risk import (
    annualized_volatility_pct,
    calmar_ratio,
    sharpe_ratio,
    sortino_ratio,
)
from engine.metrics.drawdown import calculate_drawdown_metrics
from engine.metrics.trade_stats import calculate_trade_statistics

__all__ = [
    # Models
    "Bar",
    "Order",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "TimeInForce",
    "Trade",
    "Position",
    "PositionSide",
    "Account",
    # Data Feeds
    "DataFeed",
    "ParquetDataFeed",
    "MemoryDataFeed",
    # Execution
    "FeeModel",
    "FillResult",
    "SlippageModel",
    "MakerTakerFeeModel",
    "FixedFeeModel",
    "ZeroFeeModel",
    "FixedBpsSlippage",
    "VolatilitySlippage",
    "ZeroSlippage",
    "ExecutionSimulator",
    # Strategy
    "Strategy",
    # Engines
    "EventDrivenEngine",
    "VectorizedEngine",
    # Analytics & Metrics
    "BacktestReport",
    "total_return_pct",
    "cagr_pct",
    "annualized_volatility_pct",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "calculate_drawdown_metrics",
    "calculate_trade_statistics",
]
