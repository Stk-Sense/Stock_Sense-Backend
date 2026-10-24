"""Trade execution record domain model."""

import uuid
from dataclasses import dataclass, field
from typing import Any
from engine.models.order import OrderSide


@dataclass(frozen=True, slots=True)
class Trade:
    """Represents an executed trade transaction."""

    order_id: uuid.UUID
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    fee: float
    timestamp: int
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    realized_pnl: float = 0.0

    @property
    def notional(self) -> float:
        """Total gross value of the trade."""
        return self.quantity * self.price

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "order_id": str(self.order_id),
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "fee": self.fee,
            "notional": self.notional,
            "timestamp": self.timestamp,
            "realized_pnl": self.realized_pnl,
        }
