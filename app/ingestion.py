import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Union
from fastapi import HTTPException
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.models import EventIn, IngestResponse, IngestError
from app.db_models import EventDB

def process_ingestion(payload: Any, db: Session) -> IngestResponse:
    # Handle both {"events": [...]} and [...] (raw list)
    raw_events = []
    if isinstance(payload, dict) and "events" in payload:
        raw_events = payload.get("events", [])
    elif isinstance(payload, list):
        raw_events = payload
    else:
        raise HTTPException(status_code=400, detail="Invalid payload format. Expected list of events or object with 'events' key.")

    if len(raw_events) > 500:
        raise HTTPException(status_code=400, detail="Batch size exceeds limit of 500 events.")

    accepted = 0
    rejected = 0
    duplicates = 0
    errors: List[IngestError] = []

    for index, raw_event in enumerate(raw_events):
        try:
            # Pydantic validation
            event_in = EventIn(**raw_event)
            
            # Check if event already exists to prevent duplicate insertion
            existing = db.query(EventDB).filter(EventDB.event_id == str(event_in.event_id)).first()
            if existing:
                duplicates += 1
                continue
                
            # Insert into database
            db_event = EventDB(
                event_id=str(event_in.event_id),
                store_id=event_in.store_id,
                camera_id=event_in.camera_id,
                visitor_id=event_in.visitor_id,
                event_type=event_in.event_type.value,
                timestamp=event_in.timestamp,
                zone_id=event_in.zone_id,
                dwell_ms=event_in.dwell_ms,
                is_staff=event_in.is_staff,
                confidence=event_in.confidence,
                metadata_json=event_in.metadata.model_dump_json() if event_in.metadata else "{}",
                created_at=datetime.now(timezone.utc)
            )
            db.add(db_event)
            db.commit()
            accepted += 1
            
        except ValidationError as e:
            rejected += 1
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                errors.append(IngestError(index=index, field=loc, message=err["msg"]))
        except Exception as e:
            db.rollback()
            rejected += 1
            errors.append(IngestError(index=index, field="unknown", message=str(e)))
            
    return IngestResponse(
        accepted=accepted,
        rejected=rejected,
        duplicates=duplicates,
        errors=errors
    )
