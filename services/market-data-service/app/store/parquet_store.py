"""Parquet storage engine with atomic writes, partitioning, and fast range reads."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from common.logging import get_logger

logger = get_logger("parquet_store")

# Strict PyArrow schema for OHLCV
CANDLE_ARROW_SCHEMA = pa.schema([
    ("ts", pa.int64()),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.float64()),
])

CANDLE_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]


def symbol_to_dirname(symbol: str) -> str:
    """Sanitize symbol for filesystem (e.g. BTC/USDT -> BTC-USDT)."""
    return symbol.replace("/", "-").upper()


def dirname_to_symbol(dirname: str) -> str:
    """Convert filesystem dirname back to pair symbol (e.g. BTC-USDT -> BTC/USDT)."""
    return dirname.replace("-", "/")


class ParquetStore:
    """Manages partitioned Parquet files with atomic merge writes and fast range queries."""

    def __init__(self, base_dir: Union[str, Path]) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_partition_dir(self, exchange: str, symbol: str, timeframe: str) -> Path:
        """Return the directory path for a specific exchange/symbol/timeframe."""
        return self.base_dir / exchange.lower() / symbol_to_dirname(symbol) / timeframe

    def _get_year_file_path(self, exchange: str, symbol: str, timeframe: str, year: int) -> Path:
        """Return the path to a yearly parquet partition."""
        return self._get_partition_dir(exchange, symbol, timeframe) / f"{year}.parquet"

    def write_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        candles: list[list[Union[int, float]]],
    ) -> int:
        """Atomically merge-write candles into yearly Parquet partitions.

        Returns:
            The number of newly added candles (excluding duplicates).
        """
        if not candles:
            return 0

        # Convert input to DataFrame
        df_new = pd.DataFrame(candles, columns=CANDLE_COLUMNS)
        df_new["ts"] = df_new["ts"].astype("int64")
        for col in ["open", "high", "low", "close", "volume"]:
            df_new[col] = df_new[col].astype("float64")

        # Extract UTC year for partitioning
        years = pd.to_datetime(df_new["ts"], unit="ms", utc=True).dt.year
        df_new["_year"] = years

        partition_dir = self._get_partition_dir(exchange, symbol, timeframe)
        partition_dir.mkdir(parents=True, exist_ok=True)

        total_added = 0

        for year, group in df_new.groupby("_year"):
            year_int = int(year)
            final_path = self._get_year_file_path(exchange, symbol, timeframe, year_int)
            new_rows = group.drop(columns=["_year"])

            if final_path.exists():
                try:
                    df_existing = pq.read_table(final_path).to_pandas()
                    combined = pd.concat([df_existing, new_rows], ignore_index=True)
                except Exception as exc:
                    logger.error(f"Failed to read existing partition {final_path}: {exc}")
                    combined = new_rows
            else:
                combined = new_rows

            # Deduplicate by ts, keeping the last occurrence, and sort ascending
            before_count = len(df_existing) if final_path.exists() else 0
            combined = combined.drop_duplicates(subset=["ts"], keep="last").sort_values("ts")
            after_count = len(combined)
            added_for_year = max(0, after_count - before_count)
            total_added += added_for_year

            # Convert to PyArrow Table with explicit schema
            table = pa.Table.from_pandas(combined, schema=CANDLE_ARROW_SCHEMA, preserve_index=False)

            # Atomic write: write to temp file then rename
            tmp_filename = f".{year_int}.parquet.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
            tmp_path = partition_dir / tmp_filename
            try:
                pq.write_table(table, tmp_path, compression="snappy")
                os.replace(tmp_path, final_path)
            except Exception as exc:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
                logger.error(f"Failed atomic write to {final_path}: {exc}")
                raise

        logger.info(
            f"Successfully merged {len(candles)} candles ({total_added} new) for {symbol} {timeframe}",
            extra={"exchange": exchange, "symbol": symbol, "timeframe": timeframe, "added": total_added},
        )
        return total_added

    def read_candles(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Read candles in [start_ts, end_ts) range across partitions."""
        partition_dir = self._get_partition_dir(exchange, symbol, timeframe)
        if not partition_dir.exists():
            return []

        # Find relevant year files
        parquet_files = sorted(partition_dir.glob("*.parquet"))
        if not parquet_files:
            return []

        # Filter by year if start_ts and/or end_ts specified
        start_year = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc).year if start_ts else None
        end_year = datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc).year if end_ts else None

        tables: list[pa.Table] = []
        for file_path in parquet_files:
            try:
                year_val = int(file_path.stem)
            except ValueError:
                continue

            if start_year and year_val < start_year:
                continue
            if end_year and year_val > end_year:
                continue

            # Read table
            try:
                tbl = pq.read_table(file_path)
                tables.append(tbl)
            except Exception as exc:
                logger.error(f"Error reading partition {file_path}: {exc}")

        if not tables:
            return []

        combined_table = pa.concat_tables(tables)
        df = combined_table.to_pandas()

        # Apply timestamp filters
        if start_ts is not None:
            df = df[df["ts"] >= start_ts]
        if end_ts is not None:
            df = df[df["ts"] < end_ts]

        df = df.sort_values("ts")

        if limit is not None and limit > 0:
            df = df.head(limit)

        return df.to_dict(orient="records")

    def get_coverage(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> tuple[Optional[int], Optional[int], int]:
        """Return (first_ts, last_ts, total_count) for the given symbol and timeframe."""
        partition_dir = self._get_partition_dir(exchange, symbol, timeframe)
        if not partition_dir.exists():
            return None, None, 0

        parquet_files = sorted([f for f in partition_dir.glob("*.parquet") if f.stem.isdigit()])
        if not parquet_files:
            return None, None, 0

        first_ts: Optional[int] = None
        last_ts: Optional[int] = None
        total_count = 0

        # Read first file to get first_ts
        first_file = parquet_files[0]
        try:
            first_table = pq.read_table(first_file, columns=["ts"])
            if len(first_table) > 0:
                first_ts = int(first_table["ts"][0].as_py())
        except Exception as exc:
            logger.error(f"Failed reading first partition {first_file}: {exc}")

        # Read last file to get last_ts
        last_file = parquet_files[-1]
        try:
            last_table = pq.read_table(last_file, columns=["ts"])
            if len(last_table) > 0:
                last_ts = int(last_table["ts"][-1].as_py())
        except Exception as exc:
            logger.error(f"Failed reading last partition {last_file}: {exc}")

        # Compute total count
        for f in parquet_files:
            try:
                metadata = pq.read_metadata(f)
                total_count += metadata.num_rows
            except Exception:
                pass

        return first_ts, last_ts, total_count

    def list_available_symbols(self, exchange: str) -> list[str]:
        """List all symbols stored on disk for an exchange."""
        exchange_dir = self.base_dir / exchange.lower()
        if not exchange_dir.exists():
            return []

        symbols = []
        for entry in exchange_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                symbols.append(dirname_to_symbol(entry.name))
        return sorted(symbols)

    def list_available_timeframes(self, exchange: str, symbol: str) -> list[str]:
        """List all timeframes available for a given exchange and symbol."""
        sym_dir = self.base_dir / exchange.lower() / symbol_to_dirname(symbol)
        if not sym_dir.exists():
            return []

        timeframes = []
        for entry in sym_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                timeframes.append(entry.name)
        return sorted(timeframes)
