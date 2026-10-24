"""Bar / Candle domain model."""

from dataclasses import dataclass
from typing import Any, Union


@dataclass(frozen=True, slots=True)
class Bar:
    """Represents a single completed OHLCV candle bar."""

    timestamp: int  # Epoch ms UTC
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str = "UNKNOWN"

    @classmethod
    def from_row(cls, row: Union[list, tuple, dict], symbol: str = "UNKNOWN") -> "Bar":
        """Instantiate a Bar from a list/tuple [ts, o, h, l, c, v] or dict."""
        if isinstance(row, dict):
            return cls(
                timestamp=int(row["ts"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                symbol=symbol,
            )
        return cls(
            timestamp=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            symbol=symbol,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "symbol": self.symbol,
        }
