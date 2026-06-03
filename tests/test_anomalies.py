# PROMPT:
# Generate pytest tests for retail anomaly detection including billing queue spike,
# conversion drop against historical average, dead zone with no visits in 30 minutes,
# severity mapping, and suggested_action strings.

# CHANGES MADE:
# I made the rules deterministic for the challenge,
# added exact threshold tests, and verified every anomaly includes suggested_action.

import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta
import uuid

from app.main import app
from app.database import Base, get_db
from app.db_models import EventDB

# Setup test DB
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

def add_event(db, store_id, visitor_id, event_type, ts, zone_id=None, metadata=None):
    if metadata is None:
        metadata = {}
    event = EventDB(
        event_id=str(uuid.uuid4()),
        store_id=store_id,
        camera_id="CAM1",
        visitor_id=visitor_id,
        event_type=event_type,
        timestamp=ts,
        zone_id=zone_id,
        dwell_ms=1000,
        is_staff=False,
        confidence=0.9,
        metadata_json=json.dumps(metadata)
    )
    db.add(event)
    db.commit()

def test_queue_spike_warn():
    db = TestingSessionLocal()
    now = datetime.utcnow()
    add_event(db, "STORE_1", "v1", "BILLING_QUEUE_JOIN", now, metadata={"queue_depth": 5})
    
    response = client.get("/stores/STORE_1/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    anomalies = data["anomalies"]
    spike_anomalies = [a for a in anomalies if a["type"] == "BILLING_QUEUE_SPIKE"]
    assert len(spike_anomalies) == 1
    assert spike_anomalies[0]["severity"] == "WARN"
    assert "suggested_action" in spike_anomalies[0]
    db.close()

def test_queue_spike_critical():
    db = TestingSessionLocal()
    now = datetime.utcnow()
    add_event(db, "STORE_2", "v1", "BILLING_QUEUE_JOIN", now, metadata={"queue_depth": 10})
    
    response = client.get("/stores/STORE_2/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    spike_anomalies = [a for a in data["anomalies"] if a["type"] == "BILLING_QUEUE_SPIKE"]
    assert len(spike_anomalies) == 1
    assert spike_anomalies[0]["severity"] == "CRITICAL"
    assert "suggested_action" in spike_anomalies[0]
    db.close()

def test_no_queue_spike():
    db = TestingSessionLocal()
    now = datetime.utcnow()
    add_event(db, "STORE_3", "v1", "BILLING_QUEUE_JOIN", now, metadata={"queue_depth": 2})
    
    response = client.get("/stores/STORE_3/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    spike_anomalies = [a for a in data["anomalies"] if a["type"] == "BILLING_QUEUE_SPIKE"]
    assert len(spike_anomalies) == 0
    db.close()

def test_dead_zone():
    db = TestingSessionLocal()
    now = datetime.utcnow()
    # A zone had an entry 40 minutes ago, but none since
    forty_mins_ago = now - timedelta(minutes=40)
    add_event(db, "STORE_4", "v1", "ZONE_ENTER", forty_mins_ago, zone_id="Z1")
    # Add a recent event in Z2 to set the DB's max timestamp correctly
    add_event(db, "STORE_4", "v2", "ZONE_ENTER", now, zone_id="Z2")
    
    response = client.get("/stores/STORE_4/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    dead_zone_anomalies = [a for a in data["anomalies"] if a["type"] == "DEAD_ZONE"]
    # Z1 is dead
    assert len(dead_zone_anomalies) >= 1
    z1_anomalies = [a for a in dead_zone_anomalies if "Z1" in a["message"]]
    assert len(z1_anomalies) == 1
    assert z1_anomalies[0]["severity"] == "WARN"
    assert "suggested_action" in z1_anomalies[0]
    
    # Z2 is not dead
    z2_anomalies = [a for a in dead_zone_anomalies if "Z2" in a["message"]]
    assert len(z2_anomalies) == 0
    db.close()

def test_conversion_drop():
    db = TestingSessionLocal()
    now = datetime.utcnow()
    
    # Baseline (2 days ago): 4 visitors, 4 converts -> 1.0 conversion rate
    two_days_ago = now - timedelta(days=2)
    for i in range(4):
        vid = f"base_v{i}"
        add_event(db, "STORE_5", vid, "ENTRY", two_days_ago)
        add_event(db, "STORE_5", vid, "BILLING_QUEUE_JOIN", two_days_ago + timedelta(minutes=5))
        
    # Today (within last 24 hrs): 10 visitors, 2 converts -> 0.2 conversion rate
    today = now - timedelta(hours=2)
    for i in range(10):
        vid = f"today_v{i}"
        add_event(db, "STORE_5", vid, "ENTRY", today)
        if i < 2:
            add_event(db, "STORE_5", vid, "BILLING_QUEUE_JOIN", today + timedelta(minutes=5))
            
    # Also add an event exactly at `now` to anchor the `now` timestamp computation
    add_event(db, "STORE_5", "anchor", "ENTRY", now)
    
    response = client.get("/stores/STORE_5/anomalies")
    assert response.status_code == 200
    data = response.json()
    
    conv_anomalies = [a for a in data["anomalies"] if a["type"] == "CONVERSION_DROP"]
    assert len(conv_anomalies) == 1
    # 0.2 < 1.0 * 0.5, so CRITICAL
    assert conv_anomalies[0]["severity"] == "CRITICAL"
    assert "suggested_action" in conv_anomalies[0]
    db.close()
