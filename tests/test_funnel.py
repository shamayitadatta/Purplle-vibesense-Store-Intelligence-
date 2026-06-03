# PROMPT:
# Generate pytest tests for a session-based retail funnel endpoint:
# Entry to Zone Visit to Billing Queue to Purchase.
# Include re-entry deduplication, staff exclusion, repeated events,
# and divide-by-zero cases.

# CHANGES MADE:
# I changed the tests to use visitor_id as the session key,
# added REENTRY events to ensure no double-counting,
# and added repeated ZONE_DWELL events for the same visitor.

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.db_models import EventDB, PosTransactionDB

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

def test_empty_funnel_returns_all_zeros():
    response = client.get("/stores/STORE_EMPTY/funnel")
    assert response.status_code == 200
    data = response.json()
    assert data["stages"]["entry"] == 0
    assert data["stages"]["zone_visit"] == 0
    assert data["stages"]["billing_queue"] == 0
    assert data["stages"]["purchase"] == 0
    assert data["dropoffs"]["entry_to_zone"]["percent"] == 0.0

def test_one_visitor_with_repeated_events_counts_once():
    events = {
        "events": [
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440001", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F1", "event_type": "ENTRY", "timestamp": "2026-03-03T14:00:00Z",
                "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440002", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F1", "event_type": "ZONE_ENTER", "timestamp": "2026-03-03T14:01:00Z",
                "zone_id": "SKINCARE", "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440003", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F1", "event_type": "ZONE_DWELL", "timestamp": "2026-03-03T14:02:00Z",
                "zone_id": "SKINCARE", "dwell_ms": 5000, "is_staff": False, "confidence": 0.9
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440004", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F1", "event_type": "BILLING_QUEUE_JOIN", "timestamp": "2026-03-03T14:05:00Z",
                "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            }
        ]
    }
    client.post("/events/ingest", json=events)
    response = client.get("/stores/STORE_BLR_002/funnel")
    data = response.json()
    assert data["stages"]["entry"] == 1
    assert data["stages"]["zone_visit"] == 1
    assert data["stages"]["billing_queue"] == 1

def test_reentry_does_not_double_count():
    events = {
        "events": [
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440005", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F2", "event_type": "ENTRY", "timestamp": "2026-03-03T14:00:00Z",
                "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440006", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F2", "event_type": "EXIT", "timestamp": "2026-03-03T14:10:00Z",
                "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440007", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F2", "event_type": "REENTRY", "timestamp": "2026-03-03T14:15:00Z",
                "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            }
        ]
    }
    client.post("/events/ingest", json=events)
    response = client.get("/stores/STORE_BLR_002/funnel")
    data = response.json()
    assert data["stages"]["entry"] == 1

def test_staff_excluded_from_all_stages():
    events = {
        "events": [
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440008", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "STAFF_02", "event_type": "ENTRY", "timestamp": "2026-03-03T14:00:00Z",
                "dwell_ms": 0, "is_staff": True, "confidence": 0.9
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440009", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "STAFF_02", "event_type": "ZONE_ENTER", "timestamp": "2026-03-03T14:05:00Z",
                "zone_id": "SKINCARE", "dwell_ms": 0, "is_staff": True, "confidence": 0.9
            }
        ]
    }
    client.post("/events/ingest", json=events)
    response = client.get("/stores/STORE_BLR_002/funnel")
    data = response.json()
    assert data["stages"]["entry"] == 0
    assert data["stages"]["zone_visit"] == 0

def test_drop_off_percentages_are_correct():
    events = {
        "events": [
            # Visitor 1 (Entry only)
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440010", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F10", "event_type": "ENTRY", "timestamp": "2026-03-03T14:00:00Z",
                "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            },
            # Visitor 2 (Entry -> Zone)
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440011", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F11", "event_type": "ENTRY", "timestamp": "2026-03-03T14:00:00Z",
                "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440012", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F11", "event_type": "ZONE_ENTER", "timestamp": "2026-03-03T14:05:00Z",
                "zone_id": "SKINCARE", "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            },
            # Visitor 3 (Entry -> Zone -> Billing Queue)
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440013", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F12", "event_type": "ENTRY", "timestamp": "2026-03-03T14:00:00Z",
                "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440014", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F12", "event_type": "ZONE_ENTER", "timestamp": "2026-03-03T14:05:00Z",
                "zone_id": "SKINCARE", "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            },
            {
                "event_id": "550e8400-e29b-41d4-a716-446655440015", "store_id": "STORE_BLR_002", "camera_id": "CAM_01",
                "visitor_id": "VIS_F12", "event_type": "BILLING_QUEUE_JOIN", "timestamp": "2026-03-03T14:15:00Z",
                "dwell_ms": 0, "is_staff": False, "confidence": 0.9
            }
        ]
    }
    client.post("/events/ingest", json=events)
    response = client.get("/stores/STORE_BLR_002/funnel")
    data = response.json()
    
    assert data["stages"]["entry"] == 3
    assert data["stages"]["zone_visit"] == 2
    assert data["stages"]["billing_queue"] == 1
    assert data["stages"]["purchase"] == 0
    
    assert data["dropoffs"]["entry_to_zone"]["count"] == 1
    assert data["dropoffs"]["entry_to_zone"]["percent"] == pytest.approx(33.33, 0.1)
    
    assert data["dropoffs"]["zone_to_billing"]["count"] == 1
    assert data["dropoffs"]["zone_to_billing"]["percent"] == 50.0
    
    assert data["dropoffs"]["billing_to_purchase"]["count"] == 1
    assert data["dropoffs"]["billing_to_purchase"]["percent"] == 100.0

def test_funnel_purchase_stage_uses_pos_matches():
    db = TestingSessionLocal()
    db.add(EventDB(
        event_id="550e8400-e29b-41d4-a716-446655440016",
        store_id="STORE_BLR_002",
        camera_id="CAM_01",
        visitor_id="VIS_BUYER",
        event_type="ENTRY",
        timestamp=datetime(2026, 3, 3, 14, 0, 0),
        zone_id=None,
        dwell_ms=0,
        is_staff=False,
        confidence=0.9,
        metadata_json="{}",
    ))
    db.add(EventDB(
        event_id="550e8400-e29b-41d4-a716-446655440017",
        store_id="STORE_BLR_002",
        camera_id="CAM_01",
        visitor_id="VIS_BUYER",
        event_type="BILLING_QUEUE_JOIN",
        timestamp=datetime(2026, 3, 3, 14, 5, 0),
        zone_id="BILLING",
        dwell_ms=0,
        is_staff=False,
        confidence=0.9,
        metadata_json='{"queue_depth": 1}',
    ))
    db.add(PosTransactionDB(
        transaction_id="TXN_TEST",
        store_id="STORE_BLR_002",
        timestamp=datetime(2026, 3, 3, 14, 6, 0),
        basket_value_inr=500.0,
        matched_visitor_id="VIS_BUYER",
    ))
    db.commit()
    db.close()

    response = client.get("/stores/STORE_BLR_002/funnel")
    data = response.json()

    assert data["stages"]["entry"] == 1
    assert data["stages"]["billing_queue"] == 1
    assert data["stages"]["purchase"] == 1
    assert data["dropoffs"]["billing_to_purchase"]["count"] == 0
