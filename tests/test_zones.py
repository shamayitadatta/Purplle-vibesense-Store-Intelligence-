# PROMPT:
# Generate pytest tests for pipeline zone geometry and store layout loading.

# CHANGES MADE:
# I mocked the json file loading and added tests for point in polygon and line crossing.

import pytest
import os
import json
from pipeline.zones import (
    load_store_layout,
    point_in_polygon,
    bbox_center,
    get_zone_for_point,
    intersect,
    crossed_entry_line,
    determine_direction
)
import pipeline.zones as zones

@pytest.fixture
def mock_layout_file(tmp_path):
    layout = {
        "stores": [
            {
                "store_id": "STORE_BLR_002",
                "zones": [
                    {
                        "zone_id": "SKINCARE",
                        "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]
                    }
                ]
            }
        ]
    }
    file_path = tmp_path / "store_layout.json"
    with open(file_path, "w") as f:
        json.dump(layout, f)
    
    # Reset cache
    zones._store_layout_cache = None
    return str(file_path)

def test_load_store_layout(mock_layout_file):
    # Test valid path
    layout = load_store_layout(mock_layout_file)
    assert "stores" in layout
    assert layout["stores"][0]["store_id"] == "STORE_BLR_002"

    # Test cache
    layout2 = load_store_layout(mock_layout_file)
    assert layout is layout2

    # Test missing path
    zones._store_layout_cache = None
    layout3 = load_store_layout("nonexistent.json")
    assert layout3 == {}

def test_point_in_polygon():
    poly = [[0, 0], [10, 0], [10, 10], [0, 10]]
    # Inside
    assert point_in_polygon((5, 5), poly) is True
    # Outside
    assert point_in_polygon((15, 15), poly) is False
    # On edge/boundary cases might vary based on ray casting, but these are clear.

def test_bbox_center():
    # x1, y1, x2, y2
    bbox = [10, 10, 20, 30]
    center = bbox_center(bbox)
    # Bottom center is (x1+x2)/2, y2
    assert center == (15.0, 30.0)

def test_get_zone_for_point(mock_layout_file):
    # Inside SKINCARE
    zone = get_zone_for_point("STORE_BLR_002", "CAM_1", (5, 5), layout_path=mock_layout_file)
    assert zone == "SKINCARE"
    
    # Outside
    zone2 = get_zone_for_point("STORE_BLR_002", "CAM_1", (15, 15), layout_path=mock_layout_file)
    assert zone2 is None
    
    # Unknown store
    zone3 = get_zone_for_point("UNKNOWN", "CAM_1", (5, 5), layout_path=mock_layout_file)
    assert zone3 is None

def test_intersect():
    # Crossing lines
    assert intersect((0, 5), (10, 5), (5, 0), (5, 10)) is True
    # Non-crossing lines
    assert intersect((0, 5), (4, 5), (5, 0), (5, 10)) is False

def test_crossed_entry_line():
    line = [[0, 5], [10, 5]]
    # Crosses
    assert crossed_entry_line((5, 0), (5, 10), line) is True
    # Does not cross
    assert crossed_entry_line((5, 0), (5, 4), line) is False
    # Missing args
    assert crossed_entry_line(None, (5, 10), line) is False

def test_determine_direction():
    line = [[0, 5], [10, 5]]
    # Y increases -> ENTRY
    assert determine_direction((5, 0), (5, 10), line) == "ENTRY"
    # Y decreases -> EXIT
    assert determine_direction((5, 10), (5, 0), line) == "EXIT"
    # Does not cross
    assert determine_direction((5, 0), (5, 4), line) is None
