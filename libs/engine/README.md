# StockSense Backtest Engine Library (`libs/engine`)

Institutional-grade, zero-look-ahead quantitative calculation engine supporting both high-speed vectorized screening and realistic event-driven simulation for cryptocurrency trading strategies.

## Features
- **Zero Look-Ahead Bias:** Strict causality enforcement. Signals at bar $t$ execute at bar $t+1$ Open.
- **Dual Execution Modes:**
  - **Vectorized Engine:** Sub-50ms matrix returns calculation for parameter sweeps and optimization.
  - **Event-Driven Engine:** High-fidelity bar-by-bar state machine simulating realistic limit fills, stop loss gaps, trailing stops, and margin liquidations.
- **Phase 1 Parquet Streaming:** Native ingestion from partitioned Parquet lakes (`data_store/{exchange}/{symbol}/{timeframe}/{year}.parquet`).
- **Institutional Market Frictions:** Maker/Taker fees, tiered volume fees, borrow funding rates, fixed bps slippage, and volatility-adjusted ATR slippage.
- **Quantitative Analytics Suite:** Sharpe, Sortino, Calmar ratios, Max Drawdown (MDD), drawdown durations, win rates, profit factor, expectancy, and serialized equity curves.
