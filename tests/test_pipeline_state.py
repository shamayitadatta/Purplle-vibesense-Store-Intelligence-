# PROMPT:
# Generate pytest tests for visitor state tracking covering entry/exit events,
# zone enter/exit/dwell events, billing queue joins, staff heuristics, and
# re-entry deduplication.
#
# CHANGES MADE:
# I adapted the tests to the challenge event catalogue, added time-based dwell
# checks, and verified REENTRY reuses the prior visitor session identity.

import pytest
from datetime import datetime, UTC
from pipeline.state import VisitorStateTracker

def test_entry_exit_generation():
    tracker = VisitorStateTracker("STORE_1", "CAM_1")
    visitor_id = "VIS_01"
    entry_line = [(0, 100), (200, 100)]
    ts = datetime.now(UTC)

    # Initial position above line (outside)
    events = tracker.update_position(visitor_id, (100, 50), ts, entry_line)
    assert len(events) == 0

    # Cross line downward (ENTRY)
    events = tracker.update_position(visitor_id, (100, 150), ts, entry_line)
    assert len(events) == 1
    assert events[0]["event_type"] == "ENTRY"

    # Stay inside
    events = tracker.update_position(visitor_id, (100, 160), ts, entry_line)
    assert len(events) == 0

    # Cross line upward (EXIT)
    events = tracker.update_position(visitor_id, (100, 50), ts, entry_line)
    assert len(events) == 1
    assert events[0]["event_type"] == "EXIT"

def test_zone_generation():
    tracker = VisitorStateTracker("STORE_1", "CAM_1")
    visitor_id = "VIS_01"
    ts = datetime.now(UTC)

    # None -> SKINCARE
    events = tracker.update_zone(visitor_id, "SKINCARE", ts)
    assert len(events) == 1
    assert events[0]["event_type"] == "ZONE_ENTER"
    assert events[0]["zone_id"] == "SKINCARE"

    # SKINCARE -> MAKEUP
    events = tracker.update_zone(visitor_id, "MAKEUP", ts)
    assert len(events) == 2
    assert events[0]["event_type"] == "ZONE_EXIT"
    assert events[0]["zone_id"] == "SKINCARE"
    assert events[1]["event_type"] == "ZONE_ENTER"
    assert events[1]["zone_id"] == "MAKEUP"

    # MAKEUP -> None
    events = tracker.update_zone(visitor_id, None, ts)
    assert len(events) == 1
    assert events[0]["event_type"] == "ZONE_EXIT"
    assert events[0]["zone_id"] == "MAKEUP"

from datetime import timedelta

def test_zone_dwell():
    tracker = VisitorStateTracker("STORE_1", "CAM_1")
    visitor_id = "VIS_01"
    
    # Enter SKINCARE at T=0
    ts0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    tracker.update_zone(visitor_id, "SKINCARE", ts0)
    
    # At T=20s, no dwell
    ts1 = ts0 + timedelta(seconds=20)
    events = tracker.update_zone(visitor_id, "SKINCARE", ts1)
    assert len(events) == 0
    
    # At T=30s, one dwell
    ts2 = ts0 + timedelta(seconds=30)
    events = tracker.update_zone(visitor_id, "SKINCARE", ts2)
    assert len(events) == 1
    assert events[0]["event_type"] == "ZONE_DWELL"
    assert events[0]["zone_id"] == "SKINCARE"
    assert events[0]["dwell_ms"] == 30000
    
    # At T=60s, second dwell
    ts3 = ts0 + timedelta(seconds=60)
    events = tracker.update_zone(visitor_id, "SKINCARE", ts3)
    assert len(events) == 1
    assert events[0]["event_type"] == "ZONE_DWELL"
    assert events[0]["dwell_ms"] == 60000

def test_billing_queue_events():
    tracker = VisitorStateTracker("STORE_1", "CAM_1")
    ts = datetime.now(UTC)

    # Visitor 1 enters BILLING
    events = tracker.update_zone("VIS_01", "BILLING", ts)
    # They should just get ZONE_ENTER, no BILLING_QUEUE_JOIN since queue_depth was 0
    event_types = [e["event_type"] for e in events]
    assert "ZONE_ENTER" in event_types
    assert "BILLING_QUEUE_JOIN" not in event_types

    # Visitor 2 enters BILLING
    events2 = tracker.update_zone("VIS_02", "BILLING", ts)
    event_types2 = [e["event_type"] for e in events2]
    assert "ZONE_ENTER" in event_types2
    assert "BILLING_QUEUE_JOIN" in event_types2
    
    # Check queue depth metadata
    join_event = next(e for e in events2 if e["event_type"] == "BILLING_QUEUE_JOIN")
    assert join_event["metadata"]["queue_depth"] == 1

    # Visitor 3 enters BILLING
    events3 = tracker.update_zone("VIS_03", "BILLING", ts)
    join_event3 = next(e for e in events3 if e["event_type"] == "BILLING_QUEUE_JOIN")
    assert join_event3["metadata"]["queue_depth"] == 2
    
    # Visitor 1 leaves BILLING
    tracker.update_zone("VIS_01", None, ts)
    assert len(tracker.billing_visitors) == 2

def test_staff_detection():
    tracker = VisitorStateTracker("STORE_1", "CAM_1")
    visitor_id = "VIS_01"
    ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

    # Short visitor (no staff)
    tracker.update_zone(visitor_id, "SKINCARE", ts)
    tracker.update_position(visitor_id, (100, 50), ts, [(0, 100), (200, 100)]) # Outside
    events = tracker.update_position(visitor_id, (100, 150), ts, [(0, 100), (200, 100)]) # Crosses to Inside (ENTRY)
    assert len(events) == 1
    assert events[0]["is_staff"] is False

    # Simulate long duration (score +2)
    ts_long = ts + timedelta(minutes=10)
    tracker.update_zone(visitor_id, "MAKEUP", ts_long)
    
    # Simulate many zones visited (score +1, total 3 -> is_staff=True)
    tracker.update_zone(visitor_id, "PERFUME", ts_long)
    tracker.update_zone(visitor_id, "CASHIER", ts_long)
    
    tracker.update_position(visitor_id, (100, 150), ts_long, [(0, 100), (200, 100)]) # Inside
    events = tracker.update_position(visitor_id, (100, 50), ts_long, [(0, 100), (200, 100)]) # Crosses to Outside (EXIT)
    # The exit event should be flagged as staff
    assert len(events) == 1
    assert events[0]["is_staff"] is True

def test_reentry_handling():
    tracker = VisitorStateTracker("STORE_1", "CAM_1")
    ts1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)

    # VIS_01 Enters
    tracker.update_position("VIS_01", (100, 50), ts1, [(0, 100), (200, 100)])
    events_enter = tracker.update_position("VIS_01", (100, 150), ts1, [(0, 100), (200, 100)])
    assert events_enter[0]["event_type"] == "ENTRY"

    # VIS_01 Exits at 10:02
    ts2 = ts1 + timedelta(minutes=2)
    events_exit = tracker.update_position("VIS_01", (100, 50), ts2, [(0, 100), (200, 100)])
    assert events_exit[0]["event_type"] == "EXIT"

    # VIS_02 Enters at 10:04 (2 mins later -> REENTRY)
    ts3 = ts1 + timedelta(minutes=4)
    tracker.update_position("VIS_02", (100, 50), ts3, [(0, 100), (200, 100)])
    events_reenter = tracker.update_position("VIS_02", (100, 150), ts3, [(0, 100), (200, 100)])
    
    assert events_reenter[0]["event_type"] == "REENTRY"
    assert events_reenter[0]["visitor_id"] == "VIS_01" # Should be aliased
    
    # Check that update_zone works with alias
    zone_events = tracker.update_zone("VIS_02", "PERFUME", ts3)
    assert zone_events[0]["visitor_id"] == "VIS_01"

    # VIS_03 Enters at 10:15 (11 mins after exit -> NEW ENTRY)
    ts4 = ts2 + timedelta(minutes=11)
    tracker.update_position("VIS_03", (100, 50), ts4, [(0, 100), (200, 100)])
    events_new = tracker.update_position("VIS_03", (100, 150), ts4, [(0, 100), (200, 100)])
    
    assert events_new[0]["event_type"] == "ENTRY"
    assert events_new[0]["visitor_id"] == "VIS_03"


