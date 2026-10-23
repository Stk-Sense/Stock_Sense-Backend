"""SQLAlchemy models for sync tracking."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Column, DateTime, Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SyncState(Base):
    """Tracks the continuous coverage range and status of each (exchange, symbol, timeframe)."""

    __tablename__ = "sync_state"

    exchange = Column(String(32), nullable=False)
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)
    first_ts = Column(BigInteger, nullable=True)
    last_ts = Column(BigInteger, nullable=True)
    status = Column(String(32), nullable=False, default="IDLE")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        PrimaryKeyConstraint("exchange", "symbol", "timeframe"),
    )


class SyncRun(Base):
    """Audit log of individual ingestion sync runs."""

    __tablename__ = "sync_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange = Column(String(32), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(16), nullable=False, index=True)
    requested_start = Column(BigInteger, nullable=True)
    requested_end = Column(BigInteger, nullable=True)
    status = Column(String(32), nullable=False, default="QUEUED", index=True)
    candles_added = Column(Integer, nullable=False, default=0)
    gaps_found = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    finished_at = Column(DateTime(timezone=True), nullable=True)
