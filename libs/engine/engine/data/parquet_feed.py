"""Parquet data feed integrating with Phase 1 market data lake."""

from pathlib import Path
from typing import Iterator, Optional, Union
import pandas as pd
import pyarrow.parquet as pq

from engine.data.base import DataFeed
from engine.models.candle import Bar


class ParquetDataFeed(DataFeed):
    """Streams bars directly from Phase 1 yearly-partitioned Parquet files."""

    def __init__(
        self,
        data_store_dir: Union[str, Path],
        symbol: str,
        timeframe: str,
        exchange: str = "binance",
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> None:
        self.data_store_dir = Path(data_store_dir).resolve()
        self._symbol = symbol
        self._timeframe = timeframe
        self._exchange = exchange.lower()
        self._start_ts = start_ts
        self._end_ts = end_ts

        self._symbol_slug = symbol.replace("/", "-").upper()
        self._partition_dir = self.data_store_dir / self._exchange / self._symbol_slug / self._timeframe
        self._df: Optional[pd.DataFrame] = None

    @property
    def symbols(self) -> list[str]:
        return [self._symbol]

    @property
    def timeframe(self) -> str:
        return self._timeframe

    def _load_data(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df

        if not self._partition_dir.exists():
            self._df = pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
            return self._df

        parquet_files = sorted(self._partition_dir.glob("*.parquet"))
        if not parquet_files:
            self._df = pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
            return self._df

        tables = []
        for p_file in parquet_files:
            try:
                tbl = pq.read_table(p_file)
                tables.append(tbl)
            except Exception:
                pass

        if not tables:
            self._df = pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
            return self._df

        import pyarrow as pa
        combined = pa.concat_tables(tables)
        df = combined.to_pandas()

        if self._start_ts is not None:
            df = df[df["ts"] >= self._start_ts]
        if self._end_ts is not None:
            df = df[df["ts"] < self._end_ts]

        df = df.sort_values("ts").reset_index(drop=True)
        self._df = df
        return self._df

    def __iter__(self) -> Iterator[Bar]:
        df = self._load_data()
        for row in df.itertuples(index=False):
            yield Bar(
                timestamp=int(row.ts),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
                symbol=self._symbol,
            )

    def to_dataframe(self) -> pd.DataFrame:
        return self._load_data().copy()

    def __len__(self) -> int:
        return len(self._load_data())
