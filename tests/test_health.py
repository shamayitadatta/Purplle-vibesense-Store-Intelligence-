# PROMPT:
# Generate pytest tests for the health endpoint covering empty databases,
# stale-feed warnings, fresh feeds, and database status reporting.

# CHANGES MADE:
# I adapted the tests to use the app's SQLite event model, override FastAPI
# dependencies with an in-memory DB, and verify STALE_FEED details per store.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta
import uuid
import os

from app.main import app
from app.database import Base, get_db
from app.db_models import EventDB

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()

def add_event(db, store_id, ts):
    event = EventDB(
        event_id=str(uuid.uuid4()),
        store_id=store_id,
        camera_id="CAM1",
        visitor_id="v1",
        event_type="ENTRY",
        timestamp=ts,
        zone_id=None,
        dwell_ms=0,
        is_staff=False,
        confidence=0.9,
        metadata_json="{}"
    )
    db.add(event)
    db.commit()

def test_health_check_empty():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["last_event_timestamp_per_store"] == {}
    assert data["warnings"] == []

def test_health_check_stale_feed():
    db = TestingSessionLocal()
    # 15 minutes ago
    ts = datetime.utcnow() - timedelta(minutes=15)
    add_event(db, "STORE_STALE", ts)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "STORE_STALE" in data["last_event_timestamp_per_store"]
    
    stale_warnings = [w for w in data["warnings"] if w["code"] == "STALE_FEED"]
    assert len(stale_warnings) == 1
    assert stale_warnings[0]["store_id"] == "STORE_STALE"
    db.close()

def test_health_check_fresh_feed():
    db = TestingSessionLocal()
    # 5 minutes ago
    ts = datetime.utcnow() - timedelta(minutes=5)
    add_event(db, "STORE_FRESH", ts)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    
    stale_warnings = [w for w in data["warnings"] if w["code"] == "STALE_FEED"]
    assert len(stale_warnings) == 0
    db.close()

def test_health_check_db_failure(monkeypatch):
    # Mock db.execute to raise an exception
    def mock_execute(*args, **kwargs):
        raise Exception("DB Connection Failed")
    
    from sqlalchemy.orm import Session
    monkeypatch.setattr(Session, "execute", mock_execute)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "error"
    assert data["status"] == "degraded"
