"""Order matching and fill simulator with realistic market dynamics."""

from engine.execution.base import FeeModel, FillResult, SlippageModel
from engine.execution.fees import MakerTakerFeeModel
from engine.execution.slippage import FixedBpsSlippage
from engine.models.candle import Bar
from engine.models.order import Order, OrderSide, OrderType


class ExecutionSimulator:
    """Evaluates pending orders against incoming price bars and simulates fills."""

    def __init__(
        self,
        fee_model: FeeModel | None = None,
        slippage_model: SlippageModel | None = None,
    ) -> None:
        self.fee_model = fee_model or MakerTakerFeeModel()
        self.slippage_model = slippage_model or FixedBpsSlippage()

    def evaluate_order(self, order: Order, bar: Bar) -> FillResult:
        """Evaluate whether a pending order fills during the bar period."""
        if not order.is_active:
            return FillResult(filled=False)

        # 1. Market Orders: Fill immediately at Bar Open with slippage
        if order.type == OrderType.MARKET:
            exec_price = self.slippage_model.calculate_slippage(order, bar, bar.open)
            fee = self.fee_model.calculate_fee(order, exec_price, order.quantity, is_maker=False)
            slippage_amt = abs(exec_price - bar.open)
            return FillResult(
                filled=True,
                fill_price=exec_price,
                fill_quantity=order.quantity,
                fee=fee,
                slippage=slippage_amt,
                timestamp=bar.timestamp,
                is_maker=False,
            )

        # 2. Limit Orders: Fill if bar price penetrated the limit price
        if order.type == OrderType.LIMIT:
            assert order.limit_price is not None
            if order.side == OrderSide.BUY:
                if bar.low <= order.limit_price:
                    # If open was already below limit, price improvement gives bar.open
                    fill_price = min(bar.open, order.limit_price)
                    fee = self.fee_model.calculate_fee(order, fill_price, order.quantity, is_maker=True)
                    return FillResult(
                        filled=True,
                        fill_price=fill_price,
                        fill_quantity=order.quantity,
                        fee=fee,
                        slippage=0.0,
                        timestamp=bar.timestamp,
                        is_maker=True,
                    )
            else:  # SELL
                if bar.high >= order.limit_price:
                    fill_price = max(bar.open, order.limit_price)
                    fee = self.fee_model.calculate_fee(order, fill_price, order.quantity, is_maker=True)
                    return FillResult(
                        filled=True,
                        fill_price=fill_price,
                        fill_quantity=order.quantity,
                        fee=fee,
                        slippage=0.0,
                        timestamp=bar.timestamp,
                        is_maker=True,
                    )

        # 3. Stop-Loss Orders: Trigger if price breaks stop barrier, execute as market order
        if order.type == OrderType.STOP_LOSS:
            assert order.stop_price is not None
            if order.side == OrderSide.SELL:
                if bar.low <= order.stop_price:
                    # Price penetrated downwards. If gapped down below stop, fill at open!
                    base_price = min(bar.open, order.stop_price)
                    exec_price = self.slippage_model.calculate_slippage(order, bar, base_price)
                    fee = self.fee_model.calculate_fee(order, exec_price, order.quantity, is_maker=False)
                    return FillResult(
                        filled=True,
                        fill_price=exec_price,
                        fill_quantity=order.quantity,
                        fee=fee,
                        slippage=abs(exec_price - base_price),
                        timestamp=bar.timestamp,
                        is_maker=False,
                    )
            else:  # BUY stop
                if bar.high >= order.stop_price:
                    base_price = max(bar.open, order.stop_price)
                    exec_price = self.slippage_model.calculate_slippage(order, bar, base_price)
                    fee = self.fee_model.calculate_fee(order, exec_price, order.quantity, is_maker=False)
                    return FillResult(
                        filled=True,
                        fill_price=exec_price,
                        fill_quantity=order.quantity,
                        fee=fee,
                        slippage=abs(exec_price - base_price),
                        timestamp=bar.timestamp,
                        is_maker=False,
                    )

        # 4. Take-Profit Orders
        if order.type == OrderType.TAKE_PROFIT:
            assert order.stop_price is not None
            if order.side == OrderSide.SELL and bar.high >= order.stop_price:
                fill_price = max(bar.open, order.stop_price)
                fee = self.fee_model.calculate_fee(order, fill_price, order.quantity, is_maker=True)
                return FillResult(
                    filled=True,
                    fill_price=fill_price,
                    fill_quantity=order.quantity,
                    fee=fee,
                    slippage=0.0,
                    timestamp=bar.timestamp,
                    is_maker=True,
                )
            elif order.side == OrderSide.BUY and bar.low <= order.stop_price:
                fill_price = min(bar.open, order.stop_price)
                fee = self.fee_model.calculate_fee(order, fill_price, order.quantity, is_maker=True)
                return FillResult(
                    filled=True,
                    fill_price=fill_price,
                    fill_quantity=order.quantity,
                    fee=fee,
                    slippage=0.0,
                    timestamp=bar.timestamp,
                    is_maker=True,
                )

        # 5. Trailing-Stop Orders
        if order.type == OrderType.TRAILING_STOP and order.trailing_delta is not None:
            if order.side == OrderSide.SELL:
                current_peak = max(order.high_water_mark or bar.open, bar.high)
                order.high_water_mark = current_peak
                dynamic_stop = current_peak * (1.0 - order.trailing_delta)
                if bar.low <= dynamic_stop:
                    base_price = min(bar.open, dynamic_stop)
                    exec_price = self.slippage_model.calculate_slippage(order, bar, base_price)
                    fee = self.fee_model.calculate_fee(order, exec_price, order.quantity, is_maker=False)
                    return FillResult(
                        filled=True,
                        fill_price=exec_price,
                        fill_quantity=order.quantity,
                        fee=fee,
                        slippage=abs(exec_price - base_price),
                        timestamp=bar.timestamp,
                        is_maker=False,
                    )
            else:  # BUY
                current_trough = min(order.high_water_mark or bar.open, bar.low)
                order.high_water_mark = current_trough
                dynamic_stop = current_trough * (1.0 + order.trailing_delta)
                if bar.high >= dynamic_stop:
                    base_price = max(bar.open, dynamic_stop)
                    exec_price = self.slippage_model.calculate_slippage(order, bar, base_price)
                    fee = self.fee_model.calculate_fee(order, exec_price, order.quantity, is_maker=False)
                    return FillResult(
                        filled=True,
                        fill_price=exec_price,
                        fill_quantity=order.quantity,
                        fee=fee,
                        slippage=abs(exec_price - base_price),
                        timestamp=bar.timestamp,
                        is_maker=False,
                    )

        return FillResult(filled=False)
