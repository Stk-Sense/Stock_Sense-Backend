# Architecture Decision Records (ADRs) — Market Data Service

## ADR 001: Float64 Precision for Candle Prices and Volume
- **Status:** Accepted (Phase 1)
- **Context:** Financial applications often debate between IEEE 754 floating-point numbers (`float64`) and fixed-point Arbitrary Precision Decimals (`decimal.Decimal` / `NUMERIC`).
- **Decision:** For historical and incremental OHLCV candle aggregations, we use 64-bit IEEE 754 floats (`pa.float64()` in Apache Arrow and `float` in Python).
- **Rationale:**
  1. OHLCV data represents historical exchange ticker prices and volume, not account balances or live order-matching execution where penny-fraction drift causes accounting discrepancies.
  2. Parquet and vectorized backtesting frameworks (NumPy, Pandas, Polars) operate with 10x-50x higher throughput and SIMD hardware acceleration on 64-bit floats compared to software-emulated Python Decimals.
  3. Execution services (Phase 9) handling live orders and balances will use precise decimal/integer units (sats/cents), while analytical pipelines consume float64 candles.

---

## ADR 002: Partitioned Parquet Lake with Atomic Rename Writes
- **Status:** Accepted (Phase 1)
- **Context:** We need a storage engine that is zero-cost, allows high-throughput range scans, and cannot be corrupted by mid-write crashes or sudden reboots.
- **Decision:**
  - Filesystem partition layout: `data_store/{exchange}/{SYMBOL}/{timeframe}/{year}.parquet`.
  - Atomicity protocol: New data is merged into existing records, deduplicated on timestamp, sorted ascending, written to a temporary file (`.{year}.parquet.tmp.{pid}.{uuid}`), and replaced via POSIX `os.replace()`.
- **Consequences:** Under POSIX semantics, `os.replace` is an atomic filesystem operation. A power cut or process termination midway either leaves the old intact file or the new complete file, never a corrupted fragment.

---

## ADR 003: Strict Forming-Candle Exclusion (Look-Ahead Bias Elimination)
- **Status:** Accepted (Phase 1)
- **Context:** Crypto exchanges return the currently active, incomplete candle (where $ts \le now < ts + tf\_ms$) in standard `fetch_ohlcv` queries.
- **Decision:** The downloader enforces the invariant:
  $$\text{Include candle if and only if: } ts + tf\_ms \le now\_utc\_ms$$
- **Consequences:** Incomplete candles are never written to disk or database. Downstream backtest engines (Phase 2+) are physically protected from look-ahead bias and incomplete volume calculations.

---

## ADR 004: "Report, Don't Fabricate" Data Quality Policy
- **Status:** Accepted (Phase 1)
- **Context:** Exchanges sometimes experience maintenance windows, downtime, or temporary data gaps.
- **Decision:** Missing intervals are detected and logged in `sync_runs.gaps_found` and exposed via `/v1/data-status`. The service **never** synthesizes, interpolates, or fabricates fake candles.
- **Consequences:** Consumers and backtests always receive authentic historical facts and are informed of exchange gaps instead of being silently misled.

---

## ADR 005: Swappable ExchangeClient Abstraction
- **Status:** Accepted (Phase 1)
- **Context:** Initial implementation targets Binance via CCXT, but future phases may need Bybit, Kraken, OKX, or custom institutional feeds.
- **Decision:** All downloader and syncer logic interacts exclusively with the abstract `ExchangeClient` protocol.
- **Consequences:** New exchanges or deterministic mock exchanges can be plugged in without changing downloader, validator, or storage modules.
