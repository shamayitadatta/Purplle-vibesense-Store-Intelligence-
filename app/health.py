from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.db_models import EventDB
from app.models import HealthResponse
import os

def get_health_status(db: Session) -> HealthResponse:
    status = "ok"
    database = "ok"
    warnings = []
    last_event_timestamp_per_store = {}
    
    # 1. Database check
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database = "error"
        status = "degraded"
        
    if database == "ok":
        # 2. Get last event per store
        results = db.query(
            EventDB.store_id, 
            func.max(EventDB.timestamp)
        ).group_by(EventDB.store_id).all()
        
        now = datetime.utcnow()
        # You can override STALE_FEED_MINUTES via env
        stale_threshold = int(os.getenv("STALE_FEED_MINUTES", "10"))
        
        for store_id, max_ts in results:
            if store_id and max_ts:
                # Store in ISO 8601 string
                last_event_timestamp_per_store[store_id] = max_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
                
                # Check stale feed
                if now - max_ts > timedelta(minutes=stale_threshold):
                    warnings.append({
                        "store_id": store_id,
                        "code": "STALE_FEED",
                        "message": f"No events received in more than {stale_threshold} minutes."
                    })

    return HealthResponse(
        status=status,
        database=database,
        last_event_timestamp_per_store=last_event_timestamp_per_store,
        warnings=warnings
    )
