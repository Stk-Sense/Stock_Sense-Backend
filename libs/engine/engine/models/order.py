"""Order domain models and lifecycle states."""

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TimeInForce(str, Enum):
    GTC = "GTC"  # Good 'Til Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill


@dataclass
class Order:
    """Represents a trading order in the execution lifecycle."""

    symbol: str
    side: OrderSide
    type: OrderType
    quantity: float
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trailing_delta: Optional[float] = None
    high_water_mark: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    created_at: int = 0  # timestamp ms
    filled_at: Optional[int] = None
    filled_quantity: float = 0.0
    filled_avg_price: float = 0.0
    fee_paid: float = 0.0
    reduce_only: bool = False
    reject_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"Order quantity must be positive, got {self.quantity}")
        if self.type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("Limit orders require a limit_price")
        if self.type in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT) and self.stop_price is None:
            raise ValueError(f"{self.type} orders require a stop_price")

    @property
    def is_active(self) -> bool:
        """Returns True if order is waiting to be matched."""
        return self.status in (OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED)

    def fill(self, fill_qty: float, fill_price: float, fee: float, timestamp: int) -> None:
        """Process a fill on this order."""
        total_qty = self.filled_quantity + fill_qty
        if total_qty > self.quantity + 1e-9:
            raise ValueError(f"Overfill: filled {total_qty} exceeds order qty {self.quantity}")

        # Compute volume-weighted average price
        self.filled_avg_price = (
            (self.filled_avg_price * self.filled_quantity) + (fill_price * fill_qty)
        ) / total_qty
        self.filled_quantity = total_qty
        self.fee_paid += fee
        self.filled_at = timestamp

        if abs(self.filled_quantity - self.quantity) < 1e-9:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED

    def cancel(self) -> None:
        if self.is_active:
            self.status = OrderStatus.CANCELLED

    def reject(self, reason: str) -> None:
        self.status = OrderStatus.REJECTED
        self.reject_reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.type.value,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "created_at": self.created_at,
            "filled_at": self.filled_at,
            "filled_quantity": self.filled_quantity,
            "filled_avg_price": self.filled_avg_price,
            "fee_paid": self.fee_paid,
        }
