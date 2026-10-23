# StockSense Market Data Service

Institutional-grade cryptocurrency historical and incremental OHLCV market data service.

## Key Features
- **Zero-Cost Historical & Incremental Ingestion:** Automated CCXT downloads with exponential backoff and rate-limit handling.
- **Look-Ahead Bias Elimination:** Drops currently forming candles ($ts + tf\_ms \le now$) to guarantee zero incomplete data reaches backtests.
- **Atomic Parquet Lake:** Yearly-partitioned Snappy-compressed Parquet files written via temporary files and POSIX `os.replace` to eliminate corruption risks.
- **Institutional Data Quality:** Enforces numeric types, monotonic order, timestamp alignment ($ts \pmod{tf\_ms} == 0$), price sanity ($low \le open, close \le high$), volume $\ge 0$, and gap reporting without fake data fabrication.
- **High-Performance REST API:** Fast columnar JSON endpoints with cursor pagination for historical queries.
- **Concurrency Safe:** PostgreSQL advisory locking prevents overlapping sync jobs for the same symbol and timeframe.
- **Prometheus Metrics & Structured Logging:** Observability endpoints with request correlation IDs propagated across services.

---

## Data Layout

Candles are stored in partitioned Parquet files:
```
data_store/
└── {exchange}/               # e.g. binance, bybit
    └── {SYMBOL}/             # e.g. BTC-USDT (slashes replaced with hyphens)
        └── {timeframe}/      # e.g. 1h, 1d, 15m, 4h
            ├── 2023.parquet
            ├── 2024.parquet
            └── 2025.parquet
```

### Arrow / Parquet Schema
| Column | Type | Description |
|---|---|---|
| `ts` | `int64` | Candle open timestamp in epoch milliseconds (UTC) |
| `open` | `float64` | Opening price |
| `high` | `float64` | Highest price during interval |
| `low` | `float64` | Lowest price during interval |
| `close` | `float64` | Closing price |
| `volume` | `float64` | Volume traded in base asset |

---

## Configuration & Environment Variables

All settings are configured via environment variables (or `.env` file):

| Variable | Default | Description |
|---|---|---|
| `EXCHANGE_ID` | `binance` | CCXT exchange identifier (e.g. `binance`, `bybit`, `kraken`) |
| `DATA_STORE_DIR` | `/app/data_store` | Path to the Parquet data lake directory |
| `DATABASE_URL` | `postgresql+psycopg2://...` | Connection URI for PostgreSQL metadata |
| `REDIS_URL` | `redis://...` | Connection URI for Redis |
| `ADMIN_API_KEY` | `dev-admin-secret-key-12345` | Secret token required for `/v1/admin/*` endpoints |
| `DEFAULT_SYMBOLS` | `BTC/USDT,ETH/USDT` | Comma-separated list of active symbols to sync |
| `DEFAULT_TIMEFRAMES` | `1h,1d,15m,4h` | Comma-separated list of active timeframes |
| `ENABLE_SCHEDULER` | `true` | Enable periodic background incremental syncs |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## How to Add a Symbol

To add a new cryptocurrency pair (e.g., `SOL/USDT`):

1. **Option A: Via Environment Variable**  
   Update `DEFAULT_SYMBOLS` in `Stock_Sense_Infra/.env`:
   ```bash
   DEFAULT_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT
   ```
   Restart the service or container. The background scheduler will automatically pick it up.

2. **Option B: Via Admin API On-Demand**  
   Trigger a historical or incremental sync using the admin endpoint:
   ```bash
   curl -X POST "http://localhost:8001/v1/admin/sync" \
     -H "X-API-Key: dev-admin-secret-key-12345" \
     -H "Content-Type: application/json" \
     -d '{"symbol": "SOL/USDT", "timeframe": "1h"}'
   ```

---

## How to Switch Exchanges

The service uses an abstract `ExchangeClient` interface. To switch the underlying exchange:

1. Update `EXCHANGE_ID` in `Stock_Sense_Infra/.env`:
   ```bash
   EXCHANGE_ID=bybit
   # or EXCHANGE_ID=kraken
   ```
2. The `CCXTExchangeClient` dynamically loads the CCXT driver for that exchange.
3. Data will be saved cleanly under `data_store/{exchange}/...`, keeping data from different exchanges completely isolated.

---

## Running Locally

### 1. Using Python Virtual Environment
```bash
cd Stock_Sense_Backend
source .venv/bin/activate
export PYTHONPATH=services/market-data-service:libs/common-py
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Running Test Suite
```bash
cd Stock_Sense_Backend
PYTHONPATH=services/market-data-service:libs/common-py .venv/bin/pytest services/market-data-service/tests -v
```

### 3. Using Docker Compose
```bash
cd Stock_Sense_Infra
docker compose up -d
```
Check health:
```bash
curl http://localhost:8001/v1/health
curl http://localhost:8001/v1/ready
```

---

## API Summary

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/v1/health` | Liveness healthcheck | None |
| `GET` | `/v1/ready` | Readiness probe (DB & storage accessibility) | None |
| `GET` | `/v1/metrics` | Prometheus metrics export | None |
| `GET` | `/v1/symbols` | Catalog of available symbols & coverage | None |
| `GET` | `/v1/candles` | Columnar JSON candle data (cursor-paginated) | None |
| `GET` | `/v1/data-status` | Coverage timestamps, candle count & health | None |
| `POST` | `/v1/admin/sync` | Trigger asynchronous historical/incremental sync | `X-API-Key` |
| `GET` | `/v1/admin/sync/{run_id}` | Poll sync run progress and metrics | `X-API-Key` |
