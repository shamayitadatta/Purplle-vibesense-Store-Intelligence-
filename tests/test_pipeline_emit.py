# PROMPT:
# Generate pytest tests for pipeline event helpers covering polygon geometry,
# bbox center calculation, line crossing, direction detection, schema validation,
# unique event IDs, and JSONL writing.
#
# CHANGES MADE:
# I adjusted the tests to validate against the API's Pydantic schema and added
# JSONL round-trip checks so emitted events match ingestion expectations.

import pytest
from pipeline.zones import (
    point_in_polygon,
    bbox_center,
    crossed_entry_line,
    determine_direction
)
from pipeline.emit import make_event, validate_event_with_api_schema, write_event_jsonl
from datetime import datetime
import tempfile
import os

def test_point_inside_polygon():
    polygon = [[100, 100], [400, 100], [400, 400], [100, 400]]
    point = (200, 200)
    assert point_in_polygon(point, polygon) is True

def test_point_outside_polygon():
    polygon = [[100, 100], [400, 100], [400, 400], [100, 400]]
    point = (50, 50)
    assert point_in_polygon(point, polygon) is False

def test_bbox_bottom_center():
    bbox = [100, 200, 300, 400]
    assert bbox_center(bbox) == (200.0, 400.0)

def test_entry_line_crossing_direction():
    # line from (0, 100) to (200, 100)
    line = [(0, 100), (200, 100)]
    
    # prev is above line (y=50), curr is below line (y=150)
    # y increases, so it crosses 'ENTRY' based on our simple heuristic
    prev_point = (100, 50)
    curr_point = (100, 150)
    
    assert crossed_entry_line(prev_point, curr_point, line) is True
    assert determine_direction(prev_point, curr_point, line) == "ENTRY"
    
    # prev is below line (y=150), curr is above line (y=50)
    # y decreases, so it crosses 'EXIT'
    prev_point2 = (100, 150)
    curr_point2 = (100, 50)
    
    assert crossed_entry_line(prev_point2, curr_point2, line) is True
    assert determine_direction(prev_point2, curr_point2, line) == "EXIT"

def test_make_event_and_validate():
    # Create event
    event = make_event(
        store_id="STORE_1",
        camera_id="CAM_1",
        visitor_id="v_1",
        event_type="ENTRY",
        timestamp=datetime(2026, 3, 3, 10, 0, 0),
        zone_id="Z1",
        dwell_ms=1000,
        is_staff=False,
        confidence=0.95,
        metadata={"key": "value"}
    )
    
    # Check fields exist
    assert "event_id" in event
    assert event["store_id"] == "STORE_1"
    assert event["confidence"] == 0.95
    assert event["metadata"] == {"key": "value"}
    
    # Validate with API schema
    validated = validate_event_with_api_schema(event)
    assert validated["store_id"] == "STORE_1"

def test_event_id_unique():
    e1 = make_event("S1", "C1", "v1", "ENTRY", datetime.utcnow())
    e2 = make_event("S1", "C1", "v1", "ENTRY", datetime.utcnow())
    assert e1["event_id"] != e2["event_id"]

def test_write_event_jsonl():
    e = make_event("S1", "C1", "v1", "ENTRY", datetime.utcnow())
    tmp = tempfile.mktemp(suffix=".jsonl")
    write_event_jsonl(e, tmp)
    
    assert os.path.exists(tmp)
    with open(tmp, "r") as f:
        line = f.read()
        assert "event_id" in line
        assert "S1" in line
    os.remove(tmp)
