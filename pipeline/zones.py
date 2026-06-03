import json
import os

_store_layout_cache = None

def load_store_layout(path="data/store_layout.json"):
    global _store_layout_cache
    if _store_layout_cache is not None:
        return _store_layout_cache
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        _store_layout_cache = json.load(f)
    return _store_layout_cache

def point_in_polygon(point, polygon):
    """Ray casting algorithm to determine if point is inside a polygon."""
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # Avoid division by zero with small epsilon
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-9) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside

def bbox_center(bbox):
    """Return bottom-center of bounding box [x1, y1, x2, y2]"""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)

def get_zone_for_point(store_id, camera_id, point, layout_path="data/store_layout.json"):
    layout = load_store_layout(layout_path)
    stores = layout.get("stores", [])
    for store in stores:
        if store.get("store_id") == store_id:
            for zone in store.get("zones", []):
                poly = zone.get("polygon")
                if poly and point_in_polygon(point, poly):
                    return zone.get("zone_id")
    return None

def ccw(A, B, C):
    """Check if three points are listed in a counterclockwise order"""
    return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])

def intersect(A, B, C, D):
    """Check if line segment A-B intersects with line segment C-D"""
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

def crossed_entry_line(prev_point, curr_point, line):
    """Check if segment (prev_point, curr_point) crosses the entry line (pointC, pointD)"""
    if not prev_point or not curr_point or not line:
        return False
    # line is typically [C, D] where C and D are (x,y) coordinates
    C, D = line[0], line[1]
    return intersect(prev_point, curr_point, C, D)

def determine_direction(prev_point, curr_point, entry_line):
    """
    Determine direction of crossing.
    If the cross product indicates moving 'inward', return 'ENTRY'.
    Else 'EXIT'.
    This is highly dependent on how the entry line is defined.
    For simplicity, we assume crossing in +y direction is ENTRY, else EXIT.
    """
    if not crossed_entry_line(prev_point, curr_point, entry_line):
        return None
    
    # Simple heuristic: if y increases, it's ENTRY.
    if curr_point[1] > prev_point[1]:
        return "ENTRY"
    return "EXIT"
