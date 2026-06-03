import os
import json
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from app.db_models import EventDB
from app.models import HeatmapResponse, HeatmapZone

def get_store_heatmap(store_id: str, db: Session) -> HeatmapResponse:
    zones_from_layout = set()
    layout_path = os.path.join("data", "store_layout.json")
    if os.path.exists(layout_path):
        try:
            with open(layout_path, "r") as f:
                layout = json.load(f)
                zones_from_layout = {z["zone_id"] for z in layout.get("zones", [])}
        except Exception:
            pass

    # Total sessions in window
    total_sessions = db.query(func.count(distinct(EventDB.visitor_id)))\
        .filter(EventDB.store_id == store_id).scalar() or 0

    data_confidence = "LOW" if total_sessions < 20 else "HIGH"

    # Query visits and dwell time per zone
    # We will just group by zone_id.
    stats = db.query(
        EventDB.zone_id,
        func.count(EventDB.event_id).label("visit_count"),
        func.avg(EventDB.dwell_ms).label("avg_dwell_ms")
    ).filter(
        EventDB.store_id == store_id,
        EventDB.zone_id.isnot(None)
    ).group_by(EventDB.zone_id).all()

    zone_data_map = {}
    for row in stats:
        if row.zone_id:
            zone_data_map[row.zone_id] = {
                "visit_count": row.visit_count,
                "avg_dwell_ms": float(row.avg_dwell_ms or 0)
            }
            zones_from_layout.add(row.zone_id)

    raw_scores = {}
    max_raw_score = 0.0

    for z in zones_from_layout:
        data = zone_data_map.get(z, {"visit_count": 0, "avg_dwell_ms": 0.0})
        visit_count = data["visit_count"]
        avg_dwell_seconds = data["avg_dwell_ms"] / 1000.0
        raw_score = visit_count * 0.6 + avg_dwell_seconds * 0.4
        raw_scores[z] = raw_score
        if raw_score > max_raw_score:
            max_raw_score = raw_score

    zones_result = []
    for z in zones_from_layout:
        data = zone_data_map.get(z, {"visit_count": 0, "avg_dwell_ms": 0.0})
        if max_raw_score > 0:
            normalized = (raw_scores[z] / max_raw_score) * 100.0
        else:
            normalized = 0.0
            
        zones_result.append(
            HeatmapZone(
                zone_id=z,
                visit_count=data["visit_count"],
                avg_dwell_ms=data["avg_dwell_ms"],
                normalized_score=round(normalized, 2),
                data_confidence=data_confidence
            )
        )

    # Sort zones by zone_id for consistent output
    zones_result.sort(key=lambda x: x.zone_id)

    return HeatmapResponse(
        store_id=store_id,
        zones=zones_result
    )
