"""Abstract ExchangeClient interface."""

from abc import ABC, abstractmethod
from typing import Any, Optional, Union


class ExchangeClient(ABC):
    """Abstract interface for cryptocurrency exchange clients."""

    @property
    @abstractmethod
    def exchange_id(self) -> str:
        """The identifier of the exchange (e.g. 'binance')."""
        pass

    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[list[Union[int, float]]]:
        """Fetch historical OHLCV candles from the exchange.

        Returns:
            List of candles, where each candle is:
            [timestamp_ms, open, high, low, close, volume]
        """
        pass

    @abstractmethod
    def fetch_markets(self) -> list[str]:
        """Fetch list of supported pair symbols."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up resources and connections."""
        pass
