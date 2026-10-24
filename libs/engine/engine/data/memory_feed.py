"""In-memory data feed for fast simulation and testing."""

from typing import Iterable, Iterator, Sequence, Union
import pandas as pd
from engine.data.base import DataFeed
from engine.models.candle import Bar


class MemoryDataFeed(DataFeed):
    """Feeds bars directly from an in-memory sequence or DataFrame."""

    def __init__(
        self,
        data: Union[Sequence[Bar], Sequence[Sequence[Union[int, float]]], pd.DataFrame],
        symbol: str = "BTC/USDT",
        timeframe: str = "1h",
    ) -> None:
        self._symbol = symbol
        self._timeframe = timeframe
        self._bars: list[Bar] = []

        if isinstance(data, pd.DataFrame):
            df_sorted = data.sort_values("ts" if "ts" in data.columns else "timestamp")
            for row in df_sorted.itertuples(index=False):
                ts = getattr(row, "ts", getattr(row, "timestamp", 0))
                self._bars.append(
                    Bar(
                        timestamp=int(ts),
                        open=float(row.open),
                        high=float(row.high),
                        low=float(row.low),
                        close=float(row.close),
                        volume=float(row.volume),
                        symbol=self._symbol,
                    )
                )
        elif data and isinstance(data[0], Bar):
            self._bars = sorted(data, key=lambda b: b.timestamp)
        else:
            sorted_raw = sorted(data, key=lambda r: r[0])
            self._bars = [Bar.from_row(r, symbol=self._symbol) for r in sorted_raw]

    @property
    def symbols(self) -> list[str]:
        return [self._symbol]

    @property
    def timeframe(self) -> str:
        return self._timeframe

    def __iter__(self) -> Iterator[Bar]:
        return iter(self._bars)

    def to_dataframe(self) -> pd.DataFrame:
        records = [b.to_dict() for b in self._bars]
        return pd.DataFrame(records)

    def __len__(self) -> int:
        return len(self._bars)
