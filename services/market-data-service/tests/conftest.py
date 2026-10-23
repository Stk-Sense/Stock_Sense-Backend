"""Pytest configuration and shared test fixtures."""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.exchange.fake_client import FakeExchangeClient
from app.main import app
from app.models.db import get_db
from app.models.sync import Base
from app.store.parquet_store import ParquetStore


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for Parquet storage."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        original = settings.DATA_STORE_DIR
        settings.DATA_STORE_DIR = tmp_dir
        yield tmp_dir
        settings.DATA_STORE_DIR = original


@pytest.fixture
def test_db_session():
    """Create an isolated in-memory SQLite database session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fake_exchange():
    """Create a clean FakeExchangeClient."""
    return FakeExchangeClient("test_binance")


@pytest.fixture
def client(test_db_session, temp_data_dir):
    """FastAPI TestClient with overridden DB session and temporary data store."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
