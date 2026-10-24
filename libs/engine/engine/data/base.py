"""Abstract DataFeed interface."""

from abc import ABC, abstractmethod
from typing import Iterator
import pandas as pd
from engine.models.candle import Bar


class DataFeed(ABC):
    """Abstract base class for streaming market data bars into backtest engines."""

    @property
    @abstractmethod
    def symbols(self) -> list[str]:
        """List of symbols present in this data feed."""
        pass

    @property
    @abstractmethod
    def timeframe(self) -> str:
        """Timeframe string of this feed."""
        pass

    @abstractmethod
    def __iter__(self) -> Iterator[Bar]:
        """Iterate over bars in strictly ascending chronological order."""
        pass

    @abstractmethod
    def to_dataframe(self) -> pd.DataFrame:
        """Load the entire feed into a Pandas DataFrame."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Total number of bars available in this feed."""
        pass
