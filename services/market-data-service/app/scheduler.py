"""Background scheduler for periodic incremental market data synchronization."""

from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.exchange.ccxt_client import CCXTExchangeClient
from app.ingest.syncer import Syncer
from app.models.db import SessionLocal
from app.store.parquet_store import ParquetStore
from common.logging import get_logger

logger = get_logger("scheduler")


class MarketDataScheduler:
    """Manages periodic background sync for active symbols and timeframes."""

    def __init__(self) -> None:
        self._scheduler: Optional[BackgroundScheduler] = None

    def _sync_all_active_pairs(self) -> None:
        """Run incremental sync across all configured symbols and timeframes."""
        logger.info("Executing periodic incremental market data sync job.")
        db = SessionLocal()
        client = CCXTExchangeClient(settings.EXCHANGE_ID)
        store = ParquetStore(settings.DATA_STORE_DIR)
        syncer = Syncer(client, store, db)

        try:
            for symbol in settings.DEFAULT_SYMBOLS:
                for tf in settings.DEFAULT_TIMEFRAMES:
                    try:
                        result = syncer.sync(symbol=symbol, timeframe=tf)
                        logger.debug(f"Periodic sync for {symbol} {tf}: {result.get('status')}")
                    except Exception as exc:
                        logger.error(f"Error in scheduled sync for {symbol} {tf}: {exc}")
        finally:
            client.close()
            db.close()

    def start(self) -> None:
        """Start the background scheduler."""
        if not settings.ENABLE_SCHEDULER:
            logger.info("Scheduler is disabled via configuration.")
            return

        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            self._sync_all_active_pairs,
            "interval",
            seconds=settings.SCHEDULER_INTERVAL_SECONDS,
            id="periodic_candle_sync",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(f"Scheduler started with interval={settings.SCHEDULER_INTERVAL_SECONDS}s.")

    def shutdown(self) -> None:
        """Gracefully stop the background scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped.")


scheduler = MarketDataScheduler()
