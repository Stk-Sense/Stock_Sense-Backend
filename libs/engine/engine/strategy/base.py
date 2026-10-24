"""Abstract Strategy interface for event-driven trading strategies."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from engine.models.candle import Bar
from engine.models.order import Order, OrderSide, OrderType
from engine.models.position import Position
from engine.models.trade import Trade


class Strategy(ABC):
    """Abstract base class for quantitative trading strategies."""

    def __init__(self) -> None:
        self._engine: Any = None
        self.context: dict[str, Any] = {}

    def _set_engine(self, engine: Any) -> None:
        self._engine = engine

    def on_start(self) -> None:
        """Called once before the backtest loop starts."""
        pass

    @abstractmethod
    def on_bar(self, bar: Bar) -> None:
        """Called for every completed bar in strictly sequential order."""
        pass

    def on_trade(self, trade: Trade) -> None:
        """Called immediately after an order is filled."""
        pass

    def on_order_status(self, order: Order) -> None:
        """Called when an order state changes (e.g. cancelled, rejected)."""
        pass

    def on_finish(self) -> None:
        """Called once after the entire data feed has been processed."""
        pass

    # Order Submission Helper Methods
    def buy(
        self,
        symbol: str,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        trailing_delta: Optional[float] = None,
    ) -> Order:
        """Submit a BUY order."""
        order = Order(
            symbol=symbol,
            side=OrderSide.BUY,
            type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            trailing_delta=trailing_delta,
        )
        self._engine.submit_order(order)
        return order

    def sell(
        self,
        symbol: str,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        trailing_delta: Optional[float] = None,
    ) -> Order:
        """Submit a SELL order."""
        order = Order(
            symbol=symbol,
            side=OrderSide.SELL,
            type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            trailing_delta=trailing_delta,
        )
        self._engine.submit_order(order)
        return order

    def close_position(self, symbol: str) -> Optional[Order]:
        """Liquidate any existing position for the given symbol."""
        pos = self._engine.account.get_position(symbol)
        if not pos.is_open:
            return None

        if pos.quantity > 0:
            return self.sell(symbol=symbol, quantity=pos.quantity, order_type=OrderType.MARKET)
        else:
            return self.buy(symbol=symbol, quantity=abs(pos.quantity), order_type=OrderType.MARKET)

    def cancel_order(self, order_id: Any) -> None:
        """Cancel a pending order."""
        self._engine.cancel_order(order_id)

    @property
    def account(self) -> Any:
        return self._engine.account

    @property
    def current_bar(self) -> Optional[Bar]:
        return self._engine.current_bar

    def get_position(self, symbol: str) -> Position:
        return self._engine.account.get_position(symbol)
