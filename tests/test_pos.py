# PROMPT:
# Generate pytest tests for POS correlation that match transactions to visitors
# seen in the billing zone within five minutes before purchase.

# CHANGES MADE:
# I added support for the supplied Purplle sales export format, store-code
# normalization, grouped line items, and conversion-rate assertions.

import pytest
import tempfile
import os
import csv
import uuid
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.db_models import EventDB, PosTransactionDB
from app.pos_matcher import load_and_match_pos, calculate_conversion_rate

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def add_event(db, store_id, visitor_id, event_type, ts, zone_id=None):
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
        metadata_json="{}"
    )
    db.add(event)
    db.commit()

def test_pos_correlation_within_5_minutes():
    db = TestingSessionLocal()
    # Visitor in billing at 14:37, POS at 14:40 -> Converted
    # Convert arbitrary fixed time
    base_time = datetime(2026, 3, 3, 14, 0, 0)
    
    # 1. Provide an ENTRY event so it counts towards unique visitors
    add_event(db, "STORE_1", "v1", "ENTRY", base_time + timedelta(minutes=35))
    
    # 2. Provide BILLING_QUEUE_JOIN at 14:37
    add_event(db, "STORE_1", "v1", "BILLING_QUEUE_JOIN", base_time + timedelta(minutes=37))

    # 3. Create mock CSV with POS at 14:40
    tmp_csv = tempfile.mktemp(suffix=".csv")
    with open(tmp_csv, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["store_id", "transaction_id", "timestamp", "basket_value_inr"])
        writer.writerow(["STORE_1", "tx1", (base_time + timedelta(minutes=40)).isoformat() + "Z", "100.0"])

    load_and_match_pos(db, tmp_csv)
    
    # Verify transaction is matched
    tx = db.query(PosTransactionDB).filter(PosTransactionDB.transaction_id == "tx1").first()
    assert tx is not None
    assert tx.matched_visitor_id == "v1"
    
    # Verify conversion rate = 1.0 (1 converted / 1 unique visitor)
    cr = calculate_conversion_rate("STORE_1", db)
    assert cr == 1.0
    
    os.remove(tmp_csv)
    db.close()

def test_pos_correlation_outside_5_minutes():
    db = TestingSessionLocal()
    # Visitor in billing at 14:30, POS at 14:40 -> Not converted
    base_time = datetime(2026, 3, 3, 14, 0, 0)
    
    add_event(db, "STORE_1", "v1", "ENTRY", base_time + timedelta(minutes=25))
    add_event(db, "STORE_1", "v1", "BILLING_QUEUE_JOIN", base_time + timedelta(minutes=30))

    tmp_csv = tempfile.mktemp(suffix=".csv")
    with open(tmp_csv, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["store_id", "transaction_id", "timestamp", "basket_value_inr"])
        writer.writerow(["STORE_1", "tx2", (base_time + timedelta(minutes=40)).isoformat() + "Z", "100.0"])

    load_and_match_pos(db, tmp_csv)
    
    tx = db.query(PosTransactionDB).filter(PosTransactionDB.transaction_id == "tx2").first()
    assert tx is not None
    assert tx.matched_visitor_id is None
    
    cr = calculate_conversion_rate("STORE_1", db)
    assert cr == 0.0
    
    os.remove(tmp_csv)
    db.close()

def test_pos_imports_challenge_sales_export_format():
    db = TestingSessionLocal()
    base_time = datetime(2026, 4, 10, 16, 50, 0)

    add_event(db, "STORE_BLR_002", "v1", "ENTRY", base_time - timedelta(minutes=10))
    add_event(db, "STORE_BLR_002", "v1", "ZONE_ENTER", base_time - timedelta(minutes=2), zone_id="BILLING")

    tmp_csv = tempfile.mktemp(suffix=".csv")
    with open(tmp_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["order_id", "invoice_type", "order_date", "order_time", "store_id", "store_name", "total_amount"])
        writer.writerow(["104363838", "sales", "10-04-2026", "16:50:00", "ST1008", "Brigade_Bangalore", "274.36"])
        writer.writerow(["104363838", "sales", "10-04-2026", "16:50:00", "ST1008", "Brigade_Bangalore", "99.00"])

    load_and_match_pos(db, tmp_csv)

    tx = db.query(PosTransactionDB).filter(PosTransactionDB.transaction_id == "104363838").first()
    assert tx is not None
    assert tx.store_id == "STORE_BLR_002"
    assert tx.matched_visitor_id == "v1"
    assert tx.basket_value_inr == pytest.approx(373.36)

    os.remove(tmp_csv)
    db.close()
