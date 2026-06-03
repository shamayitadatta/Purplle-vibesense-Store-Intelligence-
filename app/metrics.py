import json
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.db_models import EventDB
from app.models import MetricsResponse

def get_store_metrics(store_id: str, db: Session) -> MetricsResponse:
    # 1. Unique visitors (count distinct visitor_id from non-staff ENTRY events)
    unique_visitors = db.query(func.count(func.distinct(EventDB.visitor_id)))\
        .filter(EventDB.store_id == store_id)\
        .filter(EventDB.event_type.in_(["ENTRY", "REENTRY"]))\
        .filter(EventDB.is_staff == False)\
        .scalar() or 0

    # 2. Avg dwell per zone
    dwell_q = db.query(
        EventDB.zone_id, 
        func.avg(EventDB.dwell_ms)
    ).filter(
        EventDB.store_id == store_id,
        EventDB.event_type == "ZONE_DWELL",
        EventDB.is_staff == False,
        EventDB.zone_id.isnot(None)
    ).group_by(EventDB.zone_id).all()

    avg_dwell_per_zone = {row[0]: float(row[1]) for row in dwell_q if row[0] is not None}

    # 3. Queue depth (latest non-null metadata.queue_depth)
    queue_events = db.query(EventDB.metadata_json)\
        .filter(EventDB.store_id == store_id)\
        .filter(EventDB.event_type.in_(["BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON"]))\
        .order_by(desc(EventDB.timestamp))\
        .limit(50).all()
    
    current_queue_depth = 0
    for (meta_json,) in queue_events:
        if meta_json:
            try:
                meta = json.loads(meta_json)
                if meta.get("queue_depth") is not None:
                    current_queue_depth = meta["queue_depth"]
                    break
            except:
                pass

    # 4. Abandonment rate
    joins = db.query(func.count(EventDB.event_id))\
        .filter(EventDB.store_id == store_id, EventDB.event_type == "BILLING_QUEUE_JOIN", EventDB.is_staff == False).scalar() or 0
        
    abandons = db.query(func.count(EventDB.event_id))\
        .filter(EventDB.store_id == store_id, EventDB.event_type == "BILLING_QUEUE_ABANDON", EventDB.is_staff == False).scalar() or 0
        
    abandonment_rate = 0.0
    if joins > 0:
        abandonment_rate = float(abandons) / float(joins)

    # 5. Conversion rate (POS data pre-loaded at startup via lifespan)
    from app.pos_matcher import calculate_conversion_rate
    conversion_rate = calculate_conversion_rate(store_id, db)

    return MetricsResponse(
        store_id=store_id,
        unique_visitors=unique_visitors,
        conversion_rate=conversion_rate,
        avg_dwell_per_zone=avg_dwell_per_zone,
        current_queue_depth=current_queue_depth,
        abandonment_rate=abandonment_rate
    )
