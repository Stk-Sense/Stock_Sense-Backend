"""Execution and fill result base abstractions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from engine.models.candle import Bar
from engine.models.order import Order


@dataclass(frozen=True, slots=True)
class FillResult:
    """Outcome of order matching against an incoming bar."""

    filled: bool
    fill_price: float = 0.0
    fill_quantity: float = 0.0
    fee: float = 0.0
    slippage: float = 0.0
    timestamp: int = 0
    is_maker: bool = False


class FeeModel(ABC):
    """Abstract interface for commission and transaction fee calculations."""

    @abstractmethod
    def calculate_fee(self, order: Order, fill_price: float, fill_qty: float, is_maker: bool = False) -> float:
        """Calculate transaction fee for a fill."""
        pass


class SlippageModel(ABC):
    """Abstract interface for slippage calculation on market orders."""

    @abstractmethod
    def calculate_slippage(self, order: Order, bar: Bar, expected_price: float) -> float:
        """Return the adjusted execution price after slippage penalty."""
        pass
