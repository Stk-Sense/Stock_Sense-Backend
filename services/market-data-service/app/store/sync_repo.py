"""Repository for sync_state and sync_runs persistence, with advisory locking."""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.sync import SyncRun, SyncState
from common.logging import get_logger

logger = get_logger("sync_repo")


def compute_advisory_lock_id(exchange: str, symbol: str, timeframe: str) -> int:
    """Generate a stable 64-bit signed integer hash for Postgres advisory lock."""
    key = f"{exchange.lower()}:{symbol.upper()}:{timeframe.lower()}"
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    # Signed 64-bit int (-2^63 to 2^63 - 1)
    lock_id = int.from_bytes(digest[:8], byteorder="big", signed=True)
    return lock_id


class SyncRepository:
    """Repository handling database operations for sync state, run logs, and concurrency locking."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def acquire_advisory_lock(self, exchange: str, symbol: str, timeframe: str) -> bool:
        """Attempt to acquire a Postgres advisory lock. Returns True if acquired, False otherwise."""
        if self.db.bind.dialect.name == "postgresql":
            lock_id = compute_advisory_lock_id(exchange, symbol, timeframe)
            result = self.db.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar()
            return bool(result)
        # SQLite / in-memory fallback: use row status check
        state = self.get_sync_state(exchange, symbol, timeframe)
        if state and state.status == "RUNNING":
            return False
        return True

    def release_advisory_lock(self, exchange: str, symbol: str, timeframe: str) -> bool:
        """Release a Postgres advisory lock."""
        if self.db.bind.dialect.name == "postgresql":
            lock_id = compute_advisory_lock_id(exchange, symbol, timeframe)
            result = self.db.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id}).scalar()
            return bool(result)
        return True

    def get_sync_state(self, exchange: str, symbol: str, timeframe: str) -> Optional[SyncState]:
        """Fetch the current sync state for a symbol/timeframe."""
        return (
            self.db.query(SyncState)
            .filter(
                SyncState.exchange == exchange.lower(),
                SyncState.symbol == symbol.upper(),
                SyncState.timeframe == timeframe.lower(),
            )
            .first()
        )

    def upsert_sync_state(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        first_ts: Optional[int],
        last_ts: Optional[int],
        status: str = "IDLE",
    ) -> SyncState:
        """Create or update continuous sync state."""
        state = self.get_sync_state(exchange, symbol, timeframe)
        now_utc = datetime.now(timezone.utc)

        if not state:
            state = SyncState(
                exchange=exchange.lower(),
                symbol=symbol.upper(),
                timeframe=timeframe.lower(),
                first_ts=first_ts,
                last_ts=last_ts,
                status=status,
                updated_at=now_utc,
            )
            self.db.add(state)
        else:
            if first_ts is not None:
                if state.first_ts is None or first_ts < state.first_ts:
                    state.first_ts = first_ts
            if last_ts is not None:
                if state.last_ts is None or last_ts > state.last_ts:
                    state.last_ts = last_ts
            state.status = status
            state.updated_at = now_utc

        self.db.commit()
        self.db.refresh(state)
        return state

    def list_all_sync_states(self, exchange: Optional[str] = None) -> list[SyncState]:
        """List all sync states, optionally filtered by exchange."""
        query = self.db.query(SyncState)
        if exchange:
            query = query.filter(SyncState.exchange == exchange.lower())
        return query.all()

    def create_sync_run(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        requested_start: Optional[int] = None,
        requested_end: Optional[int] = None,
        run_id: Optional[uuid.UUID] = None,
    ) -> SyncRun:
        """Record the start of a new sync run."""
        run = SyncRun(
            id=run_id or uuid.uuid4(),
            exchange=exchange.lower(),
            symbol=symbol.upper(),
            timeframe=timeframe.lower(),
            requested_start=requested_start,
            requested_end=requested_end,
            status="RUNNING",
            candles_added=0,
            gaps_found=0,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_sync_run(
        self,
        run_id: uuid.UUID,
        status: str,
        candles_added: int = 0,
        gaps_found: int = 0,
        error: Optional[str] = None,
    ) -> Optional[SyncRun]:
        """Update a sync run with final status and metrics."""
        run = self.db.query(SyncRun).filter(SyncRun.id == run_id).first()
        if not run:
            return None

        run.status = status
        run.candles_added = candles_added
        run.gaps_found = gaps_found
        run.error = error
        run.finished_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(run)
        return run

    def get_sync_run(self, run_id: uuid.UUID) -> Optional[SyncRun]:
        """Fetch a sync run by UUID."""
        return self.db.query(SyncRun).filter(SyncRun.id == run_id).first()
