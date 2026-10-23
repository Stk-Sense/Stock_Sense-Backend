"""Data quality validation rules and gap detection."""

import math
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from app.ingest.timeframes import is_aligned, tf_to_ms
from common.logging import get_logger

logger = get_logger("quality")


class DataQualityError(Exception):
    """Raised when a batch violates non-recoverable quality checks."""
    pass


@dataclass
class ValidationResult:
    """Outcome of quality validation for a batch of candles."""
    valid_candles: list[list[Union[int, float]]] = field(default_factory=list)
    quarantined_candles: list[dict[str, Any]] = field(default_factory=list)
    duplicates_dropped: int = 0
    was_reordered: bool = False
    gaps: list[tuple[int, int]] = field(default_factory=list)  # (gap_start_ts, gap_end_ts)


def validate_batch(
    candles: list[list[Union[int, float]]],
    timeframe: str,
    previous_last_ts: Optional[int] = None,
) -> ValidationResult:
    """Validate a batch of OHLCV candles according to institutional quality rules.

    Checks:
    1. Schema & Types: 6 numeric elements, no NaN/Inf. (Reject batch on failure)
    2. Alignment: ts % tf_ms == 0. (Reject batch on failure)
    3. Ordering: strictly increasing ts. (Sort if out of order, log warning)
    4. Duplicates: unique ts. (Drop duplicates and count)
    5. Price sanity: low <= open, close <= high, all > 0. (Quarantine bad candle)
    6. Volume: volume >= 0. (Quarantine bad candle)
    7. Gaps: detect missing intervals (delta > tf_ms). (Record in result)
    """
    if not candles:
        return ValidationResult()

    tf_ms = tf_to_ms(timeframe)
    result = ValidationResult()

    # 1. Schema & Types Validation + Alignment Check
    parsed_candles = []
    for idx, row in enumerate(candles):
        if not isinstance(row, (list, tuple)) or len(row) != 6:
            msg = f"Invalid candle format at index {idx}: expected 6 elements, got {row}"
            logger.error(msg)
            raise DataQualityError(msg)

        ts, o, h, l, c, v = row
        for name, val in [("open", o), ("high", h), ("low", l), ("close", c), ("volume", v)]:
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                msg = f"Non-numeric or NaN value in candle at index {idx} ({name}={val})"
                logger.error(msg)
                raise DataQualityError(msg)

        if not isinstance(ts, int) or ts < 0:
            msg = f"Invalid timestamp at index {idx}: ts={ts}"
            logger.error(msg)
            raise DataQualityError(msg)

        if not is_aligned(ts, tf_ms):
            msg = f"Unaligned timestamp at index {idx}: ts={ts} % tf_ms({tf_ms}) != 0"
            logger.error(msg)
            raise DataQualityError(msg)

        parsed_candles.append([int(ts), float(o), float(h), float(l), float(c), float(v)])

    # 2. Ordering check & sorting
    is_sorted = all(parsed_candles[i][0] < parsed_candles[i + 1][0] for i in range(len(parsed_candles) - 1))
    if not is_sorted:
        logger.warning("Batch candles were out of chronological order. Sorting.")
        parsed_candles.sort(key=lambda x: x[0])
        result.was_reordered = True

    # 3. Deduplication
    unique_candles: list[list[Union[int, float]]] = []
    seen_ts: set[int] = set()
    for row in parsed_candles:
        row_ts = int(row[0])
        if row_ts in seen_ts:
            result.duplicates_dropped += 1
        else:
            seen_ts.add(row_ts)
            unique_candles.append(row)

    # 4. Price & Volume Sanity (Quarantine invalid candles)
    sane_candles: list[list[Union[int, float]]] = []
    for row in unique_candles:
        ts, o, h, l, c, v = row
        price_issues = []

        if o <= 0 or h <= 0 or l <= 0 or c <= 0:
            price_issues.append("Non-positive price")
        if l > o or l > c:
            price_issues.append(f"Low price ({l}) exceeds open ({o}) or close ({c})")
        if h < o or h < c:
            price_issues.append(f"High price ({h}) is lower than open ({o}) or close ({c})")
        if l > h:
            price_issues.append(f"Low price ({l}) exceeds high price ({h})")
        if v < 0:
            price_issues.append(f"Negative volume ({v})")

        if price_issues:
            logger.warning(
                f"Quarantining candle at ts={ts} due to price/volume sanity: {', '.join(price_issues)}",
                extra={"ts": ts, "candle": row, "issues": price_issues},
            )
            result.quarantined_candles.append({
                "candle": row,
                "issues": price_issues,
            })
        else:
            sane_candles.append(row)

    result.valid_candles = sane_candles

    # 5. Gap Detection
    # Check gap between previous_last_ts and the first candle of this batch
    if sane_candles:
        first_candle_ts = int(sane_candles[0][0])
        if previous_last_ts is not None and first_candle_ts > previous_last_ts + tf_ms:
            gap_start = previous_last_ts + tf_ms
            gap_end = first_candle_ts
            result.gaps.append((gap_start, gap_end))
            logger.info(
                f"Detected gap across batch boundary: missing [{gap_start}, {gap_end})",
                extra={"gap_start": gap_start, "gap_end": gap_end, "timeframe": timeframe},
            )

        # Check gaps within the batch
        for i in range(len(sane_candles) - 1):
            curr_ts = int(sane_candles[i][0])
            next_ts = int(sane_candles[i + 1][0])
            if next_ts > curr_ts + tf_ms:
                gap_start = curr_ts + tf_ms
                gap_end = next_ts
                result.gaps.append((gap_start, gap_end))
                logger.info(
                    f"Detected gap within batch: missing [{gap_start}, {gap_end})",
                    extra={"gap_start": gap_start, "gap_end": gap_end, "timeframe": timeframe},
                )

    return result
