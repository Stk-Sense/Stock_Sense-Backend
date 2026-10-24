"""Exchange commission and fee models."""

from engine.execution.base import FeeModel
from engine.models.order import Order


class MakerTakerFeeModel(FeeModel):
    """Institutional maker/taker percentage commission model.

    Example:
        maker_fee_rate = 0.0002 (2 bps / 0.02%)
        taker_fee_rate = 0.0004 (4 bps / 0.04%)
    """

    def __init__(self, maker_fee_rate: float = 0.0002, taker_fee_rate: float = 0.0004) -> None:
        self.maker_fee_rate = maker_fee_rate
        self.taker_fee_rate = taker_fee_rate

    def calculate_fee(self, order: Order, fill_price: float, fill_qty: float, is_maker: bool = False) -> float:
        rate = self.maker_fee_rate if is_maker else self.taker_fee_rate
        notional = fill_price * fill_qty
        return notional * rate


class FixedFeeModel(FeeModel):
    """Fixed dollar commission per trade execution (e.g. $1.00 per trade)."""

    def __init__(self, fee_per_trade: float = 1.0) -> None:
        self.fee_per_trade = fee_per_trade

    def calculate_fee(self, order: Order, fill_price: float, fill_qty: float, is_maker: bool = False) -> float:
        return self.fee_per_trade


class ZeroFeeModel(FeeModel):
    """Zero fee model for fee-free exchanges or baseline comparisons."""

    def calculate_fee(self, order: Order, fill_price: float, fill_qty: float, is_maker: bool = False) -> float:
        return 0.0
