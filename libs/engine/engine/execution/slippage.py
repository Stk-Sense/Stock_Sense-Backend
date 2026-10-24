"""Slippage models for realistic price impact."""

from engine.execution.base import SlippageModel
from engine.models.candle import Bar
from engine.models.order import Order, OrderSide


class ZeroSlippage(SlippageModel):
    """Zero slippage model."""

    def calculate_slippage(self, order: Order, bar: Bar, expected_price: float) -> float:
        return expected_price


class FixedBpsSlippage(SlippageModel):
    """Fixed basis points slippage model.

    Example:
        bps = 5.0 (0.05% price penalty)
    """

    def __init__(self, bps: float = 5.0) -> None:
        self.slippage_fraction = bps / 10_000.0

    def calculate_slippage(self, order: Order, bar: Bar, expected_price: float) -> float:
        if order.side == OrderSide.BUY:
            return expected_price * (1.0 + self.slippage_fraction)
        else:
            return expected_price * (1.0 - self.slippage_fraction)


class VolatilitySlippage(SlippageModel):
    """Slippage scaling proportionally with the candle's High-Low volatility range."""

    def __init__(self, range_fraction: float = 0.05) -> None:
        self.range_fraction = range_fraction

    def calculate_slippage(self, order: Order, bar: Bar, expected_price: float) -> float:
        bar_range = max(0.0, bar.high - bar.low)
        penalty = bar_range * self.range_fraction
        if order.side == OrderSide.BUY:
            return expected_price + penalty
        else:
            return max(0.00001, expected_price - penalty)
