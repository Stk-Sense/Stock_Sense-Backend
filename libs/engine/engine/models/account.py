"""Account portfolio accounting and margin management model."""

from dataclasses import dataclass, field
from typing import Any, Optional
from engine.models.order import OrderSide
from engine.models.position import Position, PositionSide
from engine.models.trade import Trade


@dataclass
class Account:
    """Manages cash balances, portfolio valuation, positions, and margin levels."""

    initial_cash: float = 100_000.0
    cash: float = field(init=False)
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    maintenance_margin_rate: float = 0.05  # 5% maintenance margin
    default_leverage: float = 1.0
    is_futures_mode: bool = False  # True for perpetual futures, False for spot cash

    def __post_init__(self) -> None:
        self.cash = float(self.initial_cash)

    @property
    def total_realized_pnl(self) -> float:
        """Sum of all realized profit/loss across closed positions."""
        return sum(t.realized_pnl for t in self.trades)

    @property
    def total_unrealized_pnl(self) -> float:
        """Mark-to-market unrealized PnL across all open positions."""
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    @property
    def equity(self) -> float:
        """Total current liquidation value of the account."""
        if self.is_futures_mode:
            return self.cash + self.total_unrealized_pnl
        # In spot mode, equity is cash + current market value of all held assets
        spot_asset_val = sum(pos.notional_value for pos in self.positions.values() if pos.side == PositionSide.LONG)
        return self.cash + spot_asset_val

    @property
    def total_margin_used(self) -> float:
        """Total margin tied up in open leveraged positions."""
        return sum(pos.margin_required for pos in self.positions.values() if pos.is_open)

    @property
    def free_margin(self) -> float:
        """Remaining margin available to open new positions."""
        return self.equity - self.total_margin_used

    @property
    def margin_level_pct(self) -> Optional[float]:
        """Equity-to-margin ratio. Higher is safer."""
        used = self.total_margin_used
        if used <= 0:
            return None
        return (self.equity / used) * 100.0

    @property
    def is_liquidatable(self) -> bool:
        """Returns True if equity falls below maintenance margin threshold."""
        if not self.is_futures_mode or self.total_margin_used <= 0:
            return self.equity <= 0
        maintenance_required = self.total_margin_used * self.maintenance_margin_rate
        return self.equity <= maintenance_required

    def get_position(self, symbol: str) -> Position:
        """Retrieve or create position object for a symbol."""
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol, leverage=self.default_leverage)
        return self.positions[symbol]

    def update_prices(self, price_map: dict[str, float]) -> None:
        """Update market prices for all tracked positions."""
        for sym, price in price_map.items():
            if sym in self.positions:
                self.positions[sym].update_market_price(price)

    def process_fill(
        self,
        order_id: Any,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        fee: float,
        timestamp: int,
    ) -> Trade:
        """Apply an executed order fill to account and position state."""
        pos = self.get_position(symbol)
        realized_pnl = pos.apply_fill(side, quantity, price)

        # Deduct transaction fee
        self.cash -= fee

        if self.is_futures_mode:
            # In derivatives/futures, cash balance changes by realized PnL
            self.cash += realized_pnl
        else:
            # In spot cash, Buying spends cash; Selling adds cash proceeds
            if side == OrderSide.BUY:
                self.cash -= (quantity * price)
            else:
                self.cash += (quantity * price)

        trade = Trade(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            timestamp=timestamp,
            realized_pnl=realized_pnl,
        )
        self.trades.append(trade)
        return trade

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "equity": self.equity,
            "total_realized_pnl": self.total_realized_pnl,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_margin_used": self.total_margin_used,
            "free_margin": self.free_margin,
            "margin_level_pct": self.margin_level_pct,
            "is_liquidatable": self.is_liquidatable,
            "positions": {sym: pos.to_dict() for sym, pos in self.positions.items()},
            "total_trades": len(self.trades),
        }
