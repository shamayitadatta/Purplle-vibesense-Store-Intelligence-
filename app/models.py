from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, UUID4
from datetime import datetime

class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"

class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: Optional[int] = None

class EventIn(BaseModel):
    event_id: UUID4
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: EventType
    timestamp: datetime
    zone_id: Optional[str] = None
    dwell_ms: int = Field(ge=0)
    is_staff: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: EventMetadata = Field(default_factory=EventMetadata)

class IngestRequest(BaseModel):
    events: List[EventIn]

class IngestError(BaseModel):
    index: int
    field: str
    message: str

class IngestResponse(BaseModel):
    accepted: int
    rejected: int
    duplicates: int
    errors: Optional[List[IngestError]] = None

class HealthResponse(BaseModel):
    status: str
    database: str
    last_event_timestamp_per_store: Dict[str, str] = {}
    warnings: List[Dict[str, str]] = []

class MetricsResponse(BaseModel):
    store_id: str
    unique_visitors: int
    conversion_rate: float
    avg_dwell_per_zone: Dict[str, float]
    current_queue_depth: int
    abandonment_rate: float

class DropoffDetails(BaseModel):
    count: int
    percent: float

class FunnelResponse(BaseModel):
    store_id: str
    stages: Dict[str, int]
    dropoffs: Dict[str, DropoffDetails]

class HeatmapZone(BaseModel):
    zone_id: str
    visit_count: int
    avg_dwell_ms: float
    normalized_score: float
    data_confidence: str

class HeatmapResponse(BaseModel):
    store_id: str
    zones: List[HeatmapZone]

class Anomaly(BaseModel):
    type: str
    severity: str
    message: str
    suggested_action: str
    detected_at: datetime

class AnomaliesResponse(BaseModel):
    store_id: str
    anomalies: List[Anomaly]
