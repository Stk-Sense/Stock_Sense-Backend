"""High-fidelity event-driven state machine backtesting engine."""

import uuid
from typing import Any, Optional
import pandas as pd

from engine.data.base import DataFeed
from engine.execution.simulator import ExecutionSimulator
from engine.metrics.drawdown import calculate_drawdown_metrics
from engine.metrics.report import BacktestReport
from engine.metrics.returns import cagr_pct, period_returns, total_return_pct
from engine.metrics.risk import (
    annualized_volatility_pct,
    calmar_ratio,
    sharpe_ratio,
    sortino_ratio,
)
from engine.metrics.trade_stats import calculate_trade_statistics
from engine.models.account import Account
from engine.models.candle import Bar
from engine.models.order import Order, OrderSide, OrderStatus, OrderType
from engine.strategy.base import Strategy


class EventDrivenEngine:
    """Orchestrates bar-by-bar causal simulation with order matching and margin tracking."""

    def __init__(
        self,
        data_feed: DataFeed,
        strategy: Strategy,
        account: Optional[Account] = None,
        simulator: Optional[ExecutionSimulator] = None,
        name: Optional[str] = None,
    ) -> None:
        self.data_feed = data_feed
        self.strategy = strategy
        self.account = account or Account()
        self.simulator = simulator or ExecutionSimulator()
        self.name = name or self.strategy.__class__.__name__

        self._pending_orders: list[Order] = []
        self._staged_orders: list[Order] = []
        self._current_bar: Optional[Bar] = None

        self.strategy._set_engine(self)

    @property
    def current_bar(self) -> Optional[Bar]:
        return self._current_bar

    def submit_order(self, order: Order) -> None:
        """Stage order for execution starting at the NEXT bar (preventing look-ahead)."""
        if self._current_bar:
            order.created_at = self._current_bar.timestamp
        self._staged_orders.append(order)

    def cancel_order(self, order_id: uuid.UUID) -> None:
        """Cancel a pending or staged order."""
        for o in self._pending_orders:
            if o.id == order_id:
                o.cancel()
                self.strategy.on_order_status(o)
                return
        for o in self._staged_orders:
            if o.id == order_id:
                o.cancel()
                self.strategy.on_order_status(o)
                return

    def run(self) -> BacktestReport:
        """Execute the event-driven backtest simulation across all bars in the data feed."""
        self.strategy.on_start()

        equity_history: list[dict[str, Any]] = []
        first_bar: Optional[Bar] = None
        last_bar: Optional[Bar] = None
        total_bars = 0

        for bar in self.data_feed:
            total_bars += 1
            if first_bar is None:
                first_bar = bar
            last_bar = bar
            self._current_bar = bar

            # 1. Update positions mark-to-market using current bar close
            self.account.update_prices({bar.symbol: bar.close})

            # 2. Margin & Forced Liquidation Check
            if self.account.is_liquidatable:
                self._force_liquidate_all(bar)
                # Snapshot after liquidation
                equity_history.append({
                    "timestamp": bar.timestamp,
                    "equity": self.account.equity,
                    "cash": self.account.cash,
                    "margin_used": self.account.total_margin_used,
                })
                continue

            # 3. Match Pending Orders against current bar
            remaining_orders: list[Order] = []
            for order in self._pending_orders:
                if not order.is_active:
                    continue

                fill_res = self.simulator.evaluate_order(order, bar)
                if fill_res.filled:
                    order.fill(
                        fill_qty=fill_res.fill_quantity,
                        fill_price=fill_res.fill_price,
                        fee=fill_res.fee,
                        timestamp=fill_res.timestamp,
                    )
                    trade = self.account.process_fill(
                        order_id=order.id,
                        symbol=order.symbol,
                        side=order.side,
                        quantity=fill_res.fill_quantity,
                        price=fill_res.fill_price,
                        fee=fill_res.fee,
                        timestamp=fill_res.timestamp,
                    )
                    self.strategy.on_trade(trade)
                    self.strategy.on_order_status(order)
                else:
                    remaining_orders.append(order)

            self._pending_orders = remaining_orders

            # 4. Strategy Step: Execute on_bar logic
            self.strategy.on_bar(bar)

            # 5. Promote staged orders to pending for the NEXT bar
            if self._staged_orders:
                self._pending_orders.extend(self._staged_orders)
                self._staged_orders = []

            # 6. Record equity snapshot at bar close
            self.account.update_prices({bar.symbol: bar.close})
            equity_history.append({
                "timestamp": bar.timestamp,
                "equity": self.account.equity,
                "cash": self.account.cash,
                "margin_used": self.account.total_margin_used,
            })

        self.strategy.on_finish()

        # Compile final analytical report
        return self._generate_report(equity_history, first_bar, last_bar, total_bars)

    def _force_liquidate_all(self, bar: Bar) -> None:
        """Liquidate all open positions due to margin call."""
        for pos in list(self.account.positions.values()):
            if pos.is_open:
                side = OrderSide.SELL if pos.quantity > 0 else OrderSide.BUY
                qty = abs(pos.quantity)
                # Fill at bar open with penalty
                exec_price = bar.open
                fee = self.simulator.fee_model.calculate_fee(
                    Order(symbol=bar.symbol, side=side, type=OrderType.MARKET, quantity=qty),
                    exec_price,
                    qty,
                    is_maker=False,
                )
                self.account.process_fill(
                    order_id=uuid.uuid4(),
                    symbol=bar.symbol,
                    side=side,
                    quantity=qty,
                    price=exec_price,
                    fee=fee,
                    timestamp=bar.timestamp,
                )
        self._pending_orders.clear()
        self._staged_orders.clear()

    def _generate_report(
        self,
        equity_history: list[dict[str, Any]],
        first_bar: Optional[Bar],
        last_bar: Optional[Bar],
        total_bars: int,
    ) -> BacktestReport:
        """Compute all quantitative statistics and aggregate report."""
        if not equity_history or first_bar is None or last_bar is None:
            return BacktestReport(
                strategy_name=self.name,
                symbol=self.data_feed.symbols[0] if self.data_feed.symbols else "UNKNOWN",
                timeframe=self.data_feed.timeframe,
                initial_cash=self.account.initial_cash,
                final_equity=self.account.initial_cash,
                total_return_pct=0.0,
                cagr_pct=0.0,
                annualized_volatility_pct=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                max_drawdown_pct=0.0,
                max_drawdown_duration_bars=0,
                trade_statistics=calculate_trade_statistics([]),
                total_bars=0,
                start_timestamp=0,
                end_timestamp=0,
                equity_curve=[],
                trades=[],
            )

        equity_df = pd.DataFrame(equity_history)
        equity_series = equity_df["equity"]
        ret_series = period_returns(equity_series)

        start_ts = first_bar.timestamp
        end_ts = last_bar.timestamp
        total_days = max(1.0, (end_ts - start_ts) / (1000.0 * 86400.0))

        tot_return = total_return_pct(self.account.initial_cash, self.account.equity)
        cagr = cagr_pct(self.account.initial_cash, self.account.equity, total_days)
        vol = annualized_volatility_pct(ret_series)
        sharpe = sharpe_ratio(ret_series)
        sortino = sortino_ratio(ret_series)
        max_dd, max_dd_dollar, max_dd_dur, underwater = calculate_drawdown_metrics(equity_series)
        calmar = calmar_ratio(cagr, max_dd)

        trade_stats = calculate_trade_statistics(self.account.trades)

        # Attach drawdown to equity curve records
        for i, row in enumerate(equity_history):
            row["drawdown_pct"] = round(float(abs(underwater.iloc[i])) * 100.0, 2)

        return BacktestReport(
            strategy_name=self.name,
            symbol=self.data_feed.symbols[0],
            timeframe=self.data_feed.timeframe,
            initial_cash=self.account.initial_cash,
            final_equity=self.account.equity,
            total_return_pct=tot_return,
            cagr_pct=cagr,
            annualized_volatility_pct=vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown_pct=max_dd,
            max_drawdown_duration_bars=max_dd_dur,
            trade_statistics=trade_stats,
            total_bars=total_bars,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            equity_curve=equity_history,
            trades=[t.to_dict() for t in self.account.trades],
        )
