# PROMPT:
# Generate pytest tests for store metrics calculation including empty stores,
# all-staff clips, average dwell per zone, queue depth, abandonment rate,
# zero purchases, and staff exclusion.
#
# CHANGES MADE:
# I rewired the generated tests to use the exact challenge event schema,
# FastAPI dependency overrides, and assertions for zero-safe metric responses.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

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

def test_empty_store_returns_zeros():
    response = client.get("/stores/STORE_EMPTY/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0
    assert data["avg_dwell_per_zone"] == {}
    assert data["current_queue_depth"] == 0
    assert data["abandonment_rate"] == 0

def test_all_staff_clip_returns_zero_customer_visitors():
    events = {
        "events": [
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440001",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "STAFF_01",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:22:10Z",
                "dwell_ms": 0,
                "is_staff": True,
                "confidence": 0.99,
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440002",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "STAFF_01",
                "event_type": "ZONE_DWELL",
                "zone_id": "SKINCARE",
                "timestamp": "2026-03-03T14:23:10Z",
                "dwell_ms": 5000,
                "is_staff": True,
                "confidence": 0.99,
            }
        ]
    }
    client.post("/events/ingest", json=events)
    
    response = client.get("/stores/STORE_BLR_002/metrics")
    data = response.json()
    assert data["unique_visitors"] == 0
    assert data["avg_dwell_per_zone"] == {}

def test_metrics_calculation_correctness():
    events = {
        "events": [
            # Visitor 1: Entry, Dwell in SKINCARE (4000ms), Join queue, Abandon
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440003",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "VIS_001",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:00:00Z",
                "dwell_ms": 0,
                "is_staff": False,
                "confidence": 0.9,
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440004",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "VIS_001",
                "event_type": "ZONE_DWELL",
                "zone_id": "SKINCARE",
                "timestamp": "2026-03-03T14:01:00Z",
                "dwell_ms": 4000,
                "is_staff": False,
                "confidence": 0.9,
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440005",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "VIS_001",
                "event_type": "BILLING_QUEUE_JOIN",
                "timestamp": "2026-03-03T14:02:00Z",
                "dwell_ms": 0,
                "is_staff": False,
                "confidence": 0.9,
                "metadata": {"queue_depth": 1}
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440006",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "VIS_001",
                "event_type": "BILLING_QUEUE_ABANDON",
                "timestamp": "2026-03-03T14:03:00Z",
                "dwell_ms": 0,
                "is_staff": False,
                "confidence": 0.9,
                "metadata": {"queue_depth": 0}
            },
            # Visitor 2: Entry, Dwell in SKINCARE (6000ms), Join queue
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440007",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "VIS_002",
                "event_type": "ENTRY",
                "timestamp": "2026-03-03T14:04:00Z",
                "dwell_ms": 0,
                "is_staff": False,
                "confidence": 0.9,
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440008",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "VIS_002",
                "event_type": "ZONE_DWELL",
                "zone_id": "SKINCARE",
                "timestamp": "2026-03-03T14:05:00Z",
                "dwell_ms": 6000,
                "is_staff": False,
                "confidence": 0.9,
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440009",
                "store_id": "STORE_BLR_002",
                "camera_id": "CAM_01",
                "visitor_id": "VIS_002",
                "event_type": "BILLING_QUEUE_JOIN",
                "timestamp": "2026-03-03T14:06:00Z",
                "dwell_ms": 0,
                "is_staff": False,
                "confidence": 0.9,
                "metadata": {"queue_depth": 3}
            }
        ]
    }
    client.post("/events/ingest", json=events)
    
    response = client.get("/stores/STORE_BLR_002/metrics")
    data = response.json()
    
    assert data["unique_visitors"] == 2
    assert data["avg_dwell_per_zone"]["SKINCARE"] == 5000.0
    assert data["current_queue_depth"] == 3
    assert data["abandonment_rate"] == 0.5  # 1 abandon / 2 joins
    assert data["conversion_rate"] == 0.0
