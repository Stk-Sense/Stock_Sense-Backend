"""Integration tests for FastAPI REST API endpoints."""

import uuid
from app.config import settings
from app.store.parquet_store import ParquetStore


def test_health_and_readiness_endpoints(client):
    # Liveness
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # Readiness
    resp = client.get("/v1/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}

    # Metrics
    resp = client.get("/v1/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]


def test_symbols_endpoint(client):
    resp = client.get("/v1/symbols")
    assert resp.status_code == 200
    data = resp.json()
    assert "symbols" in data
    assert any(s["symbol"] == "BTC/USDT" for s in data["symbols"])


def test_candles_endpoint(client, temp_data_dir):
    store = ParquetStore(temp_data_dir)
    # Seed 5 candles
    ts0 = 1704067200000
    candles = [[ts0 + (i * 3600000), 100.0, 105.0, 95.0, 102.0, 1.0] for i in range(5)]
    store.write_candles(settings.EXCHANGE_ID, "BTC/USDT", "1h", candles)

    # Valid query
    resp = client.get("/v1/candles", params={"symbol": "BTC/USDT", "timeframe": "1h"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "BTC/USDT"
    assert data["timeframe"] == "1h"
    assert data["count"] == 5
    assert len(data["data"]) == 5
    assert data["columns"] == ["ts", "open", "high", "low", "close", "volume"]

    # Invalid timeframe
    resp = client.get("/v1/candles", params={"symbol": "BTC/USDT", "timeframe": "invalid_tf"})
    assert resp.status_code == 400
    error_payload = resp.json()
    assert error_payload["error"]["code"] == "INVALID_INPUT"
    assert "correlation_id" in error_payload

    # Invalid range: start >= end
    resp = client.get(
        "/v1/candles",
        params={"symbol": "BTC/USDT", "timeframe": "1h", "start": 2000, "end": 1000},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_INPUT"


def test_data_status_endpoint(client, temp_data_dir):
    store = ParquetStore(temp_data_dir)
    ts0 = 1704067200000
    candles = [[ts0 + (i * 3600000), 100.0, 105.0, 95.0, 102.0, 1.0] for i in range(3)]
    store.write_candles(settings.EXCHANGE_ID, "ETH/USDT", "1h", candles)

    resp = client.get("/v1/data-status", params={"symbol": "ETH/USDT", "timeframe": "1h"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "ETH/USDT"
    assert data["timeframe"] == "1h"
    assert data["first_ts"] == ts0
    assert data["total_candles"] == 3


def test_admin_sync_authentication_and_status(client, monkeypatch):
    # Mock background task execution so unit test doesn't need external live network/db
    mock_called = []
    def fake_background_sync(*args, **kwargs):
        mock_called.append(args)

    monkeypatch.setattr("app.api.admin._run_background_sync", fake_background_sync)

    # Missing API Key -> 401
    resp = client.post("/v1/admin/sync", json={"symbol": "BTC/USDT", "timeframe": "1h"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"

    # Wrong API Key -> 401
    resp = client.post(
        "/v1/admin/sync",
        headers={"X-API-Key": "wrong-key"},
        json={"symbol": "BTC/USDT", "timeframe": "1h"},
    )
    assert resp.status_code == 401

    # Valid API Key -> 202 Accepted
    resp = client.post(
        "/v1/admin/sync",
        headers={"X-API-Key": settings.ADMIN_API_KEY},
        json={"symbol": "BTC/USDT", "timeframe": "1h"},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "QUEUED"
    run_id = data["run_id"]

    # Poll Sync Run Status
    status_resp = client.get(
        f"/v1/admin/sync/{run_id}",
        headers={"X-API-Key": settings.ADMIN_API_KEY},
    )
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["run_id"] == run_id

    # Unknown Run ID -> 404
    fake_id = str(uuid.uuid4())
    notFound_resp = client.get(
        f"/v1/admin/sync/{fake_id}",
        headers={"X-API-Key": settings.ADMIN_API_KEY},
    )
    assert notFound_resp.status_code == 404
    assert notFound_resp.json()["error"]["code"] == "NOT_FOUND"
