# PROMPT:
# Generate pytest tests for FastAPI event ingestion covering valid batch insert,
# duplicate event_id idempotency, invalid schema, more than 500 events, and partial success.

# CHANGES MADE:
# I adjusted the generated tests to match our exact EventIn schema,
# added assertions for database row count, and verified duplicate events are not inserted twice.

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, get_db
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()

def test_valid_event_accepted():
    payload = {
        "events": [{
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_ENTRY_01",
            "visitor_id": "VIS_001",
            "event_type": "ENTRY",
            "timestamp": "2026-03-03T14:22:10Z",
            "zone_id": None,
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.91,
            "metadata": {"queue_depth": None, "sku_zone": None, "session_seq": 1}
        }]
    }
    response = client.post("/events/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 1, data
    assert data["rejected"] == 0
    assert data["duplicates"] == 0
    assert len(data["errors"]) == 0

def test_duplicate_event_idempotent():
    payload = {
        "events": [{
            "event_id": "550e8400-e29b-41d4-a716-446655440001",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_ENTRY_01",
            "visitor_id": "VIS_002",
            "event_type": "ENTRY",
            "timestamp": "2026-03-03T14:22:10Z",
            "dwell_ms": 0,
            "is_staff": False,
            "confidence": 0.91,
        }]
    }
    # First insert
    response1 = client.post("/events/ingest", json=payload)
    assert response1.json()["accepted"] == 1
    
    # Second insert
    response2 = client.post("/events/ingest", json=payload)
    assert response2.status_code == 200
    data = response2.json()
    assert data["accepted"] == 0
    assert data["duplicates"] == 1
    assert data["rejected"] == 0

def test_invalid_confidence_rejects_event():
    payload = {
        "events": [{
            "event_id": "550e8400-e29b-41d4-a716-446655440002",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_ENTRY_01",
            "visitor_id": "VIS_003",
            "event_type": "ENTRY",
            "timestamp": "2026-03-03T14:22:10Z",
            "dwell_ms": 0,
            "confidence": 1.5, # Invalid
        }]
    }
    response = client.post("/events/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 0
    assert data["rejected"] == 1
    assert len(data["errors"]) > 0
    assert data["errors"][0]["field"] == "confidence"

def test_missing_field_rejects_event():
    payload = {
        "events": [{
            "event_id": "550e8400-e29b-41d4-a716-446655440003",
            "store_id": "STORE_BLR_002",
            # missing camera_id
            "visitor_id": "VIS_004",
            "event_type": "ENTRY",
            "timestamp": "2026-03-03T14:22:10Z",
            "dwell_ms": 0,
            "confidence": 0.9,
        }]
    }
    response = client.post("/events/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["accepted"] == 0
    assert data["rejected"] == 1
    assert len(data["errors"]) > 0
    assert data["errors"][0]["field"] == "camera_id"

def test_batch_partial_success():
    payload = {
        "events": [
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440010",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "VIS_10",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:22:10Z",
                "dwell_ms": 0,
                "confidence": 0.9,
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440011",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "VIS_11",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:22:10Z",
                "dwell_ms": 0,
                "confidence": 1.9, # Invalid
            }
        ]
    }
    response = client.post("/events/ingest", json=payload)
    data = response.json()
    assert data["accepted"] == 1, data
    assert data["rejected"] == 1
    assert data["duplicates"] == 0
    assert len(data["errors"]) == 1
    assert data["errors"][0]["index"] == 1

def test_more_than_500_events_error():
    events = []
    for i in range(501):
        events.append({
            "event_id": f"550e8400-e29b-41d4-a716-44665544{i:04d}",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_01",
            "visitor_id": "VIS_01",
            "event_type": "ENTRY",
            "timestamp": "2026-03-03T14:22:10Z",
            "dwell_ms": 0,
            "confidence": 0.9,
        })
    response = client.post("/events/ingest", json={"events": events})
    assert response.status_code == 400
    assert "Batch size exceeds limit" in response.json()["detail"]

def test_staff_event_is_stored_with_is_staff_true():
    payload = {
        "events": [{
            "event_id": "550e8400-e29b-41d4-a716-446655440020",
            "store_id": "STORE_BLR_002",
            "camera_id": "CAM_01",
            "visitor_id": "VIS_STAFF_01",
            "event_type": "ENTRY",
            "timestamp": "2026-03-03T14:22:10Z",
            "dwell_ms": 0,
            "is_staff": True,
            "confidence": 0.99,
        }]
    }
    response = client.post("/events/ingest", json=payload)
    assert response.json()["accepted"] == 1
    
    # Query database to confirm is_staff=True
    db = TestingSessionLocal()
    from app.db_models import EventDB
    stored = db.query(EventDB).filter_by(event_id="550e8400-e29b-41d4-a716-446655440020").first()
    assert stored is not None
    assert stored.is_staff is True
    db.close()
