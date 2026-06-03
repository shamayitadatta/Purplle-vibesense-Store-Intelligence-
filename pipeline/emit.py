import uuid
import json
from app.models import EventIn

def make_event(
    store_id,
    camera_id,
    visitor_id,
    event_type,
    timestamp,
    zone_id=None,
    dwell_ms=0,
    is_staff=False,
    confidence=0.0,
    metadata=None
):
    """
    Generate a schema-valid event dictionary.
    timestamp can be a datetime object or a valid ISO 8601 string.
    If it's a datetime object, we convert to string.
    """
    if metadata is None:
        metadata = {}
        
    if hasattr(timestamp, "isoformat"):
        timestamp_str = timestamp.isoformat()
        if not timestamp_str.endswith("Z") and "+" not in timestamp_str:
            timestamp_str += "Z"
    else:
        timestamp_str = str(timestamp)
        
    event = {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp_str,
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": confidence,
        "metadata": metadata
    }
    return event

def validate_event_with_api_schema(event):
    """
    Validate the event dictionary against the API schema (EventIn).
    Raises ValueError or Pydantic ValidationError if invalid.
    """
    # EventIn will validate the dictionary
    event_model = EventIn(**event)
    # We can return the validated dictionary
    return event_model.model_dump()

def write_event_jsonl(event, output_path):
    """
    Validate and append an event dictionary as a JSON line to output_path.
    """
    try:
        validated_event = validate_event_with_api_schema(event)
    except Exception as e:
        print(f"Validation failed for event: {event}")
        raise e

    # write dictionary to jsonl
    with open(output_path, "a", encoding="utf-8") as f:
        # Pydantic dump datetime to object, we want json serializable
        # We can just serialize the dict. We need to handle datetime if model_dump converts it.
        # EventIn dump converts datetime to datetime object if we don't specify mode='json'.
        # Assuming Pydantic v2
        if hasattr(EventIn, "model_dump_json"):
            # It's better to dump the model to JSON directly
            json_str = EventIn(**event).model_dump_json()
            f.write(json_str + "\n")
        else:
            # Fallback for Pydantic v1
            json_str = EventIn(**event).json()
            f.write(json_str + "\n")
