"""Incremental synchronization orchestrator with concurrency safety."""

import time
import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.exchange.base import ExchangeClient
from app.ingest.downloader import Downloader
from app.ingest.timeframes import tf_to_ms
from app.store.parquet_store import ParquetStore
from app.store.sync_repo import SyncRepository
from app.validate.quality import validate_batch
from common.logging import get_logger

logger = get_logger("syncer")


class Syncer:
    """Orchestrates incremental candle syncs with locking, validation, and storage."""

    def __init__(
        self,
        exchange_client: ExchangeClient,
        parquet_store: ParquetStore,
        db_session: Session,
    ) -> None:
        self.exchange = exchange_client
        self.store = parquet_store
        self.repo = SyncRepository(db_session)
        self.downloader = Downloader(exchange_client)

    def sync(
        self,
        symbol: str,
        timeframe: str,
        requested_start: Optional[int] = None,
        requested_end: Optional[int] = None,
        run_id: Optional[uuid.UUID] = None,
        current_time_ms: Optional[int] = None,
    ) -> dict[str, any]:
        """Execute a synchronization run for (symbol, timeframe).

        Returns:
            Dict containing sync status, candles_added, and gaps_found.
        """
        exchange = self.exchange.exchange_id
        tf_ms = tf_to_ms(timeframe)
        now_ms = current_time_ms if current_time_ms is not None else int(time.time() * 1000)

        # 1. Acquire concurrency advisory lock
        lock_acquired = self.repo.acquire_advisory_lock(exchange, symbol, timeframe)
        if not lock_acquired:
            msg = f"Sync for {exchange}:{symbol}:{timeframe} is already running."
            logger.warning(msg)
            return {"status": "CONFLICT", "message": msg, "candles_added": 0, "gaps_found": 0}

        # 2. Record sync run
        run = self.repo.create_sync_run(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            requested_start=requested_start,
            requested_end=requested_end,
            run_id=run_id,
        )

        total_candles_added = 0
        total_gaps_found = 0
        last_processed_ts: Optional[int] = None
        first_processed_ts: Optional[int] = None

        try:
            # 3. Resolve start timestamp
            state = self.repo.get_sync_state(exchange, symbol, timeframe)
            start_ts: int
            if requested_start is not None:
                start_ts = requested_start
            elif state and state.last_ts is not None:
                # Incremental sync: continue from stored last_ts + 1 timeframe
                start_ts = state.last_ts + tf_ms
            else:
                # Default initial start: 2 years ago
                start_ts = now_ms - (2 * 365 * 24 * 60 * 60 * 1000)

            # Ensure start_ts is aligned
            start_ts = (start_ts // tf_ms) * tf_ms

            # Check if already caught up
            if start_ts + tf_ms > now_ms:
                logger.info(f"Already caught up for {symbol} {timeframe}. Nothing to download.")
                self.repo.update_sync_run(run.id, status="DONE", candles_added=0, gaps_found=0)
                return {"status": "DONE", "candles_added": 0, "gaps_found": 0}

            # 4. Fetch and process in batches
            prev_ts = state.last_ts if (state and state.last_ts and requested_start is None) else None

            for batch in self.downloader.fetch_batches(
                symbol=symbol,
                timeframe=timeframe,
                start_ts=start_ts,
                end_ts=requested_end,
                current_time_ms=now_ms,
            ):
                if not batch:
                    continue

                # Validate data quality
                val_result = validate_batch(batch, timeframe=timeframe, previous_last_ts=prev_ts)
                total_gaps_found += len(val_result.gaps)

                if val_result.valid_candles:
                    # Write to Parquet data store atomically
                    added = self.store.write_candles(
                        exchange=exchange,
                        symbol=symbol,
                        timeframe=timeframe,
                        candles=val_result.valid_candles,
                    )
                    total_candles_added += added

                    if first_processed_ts is None:
                        first_processed_ts = int(val_result.valid_candles[0][0])
                    last_processed_ts = int(val_result.valid_candles[-1][0])
                    prev_ts = last_processed_ts

            # 5. Update sync state in Postgres
            disk_first, disk_last, disk_count = self.store.get_coverage(exchange, symbol, timeframe)
            self.repo.upsert_sync_state(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                first_ts=disk_first,
                last_ts=disk_last,
                status="IDLE",
            )

            # 6. Mark sync run as DONE
            self.repo.update_sync_run(
                run_id=run.id,
                status="DONE",
                candles_added=total_candles_added,
                gaps_found=total_gaps_found,
            )

            logger.info(
                f"Sync completed successfully for {symbol} {timeframe}: {total_candles_added} added, {total_gaps_found} gaps.",
                extra={"run_id": str(run.id), "added": total_candles_added, "gaps": total_gaps_found},
            )
            return {
                "status": "DONE",
                "run_id": str(run.id),
                "candles_added": total_candles_added,
                "gaps_found": total_gaps_found,
            }

        except Exception as exc:
            logger.exception(f"Sync failed for {symbol} {timeframe}: {exc}")
            self.repo.update_sync_run(
                run_id=run.id,
                status="FAILED",
                candles_added=total_candles_added,
                gaps_found=total_gaps_found,
                error=str(exc),
            )
            return {
                "status": "FAILED",
                "run_id": str(run.id),
                "error": str(exc),
                "candles_added": total_candles_added,
                "gaps_found": total_gaps_found,
            }
        finally:
            self.repo.release_advisory_lock(exchange, symbol, timeframe)
