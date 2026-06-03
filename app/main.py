import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.database import init_db, get_db, SessionLocal
from app.models import HealthResponse, MetricsResponse, FunnelResponse, HeatmapResponse, AnomaliesResponse, IngestRequest, IngestResponse
from app.ingestion import process_ingestion
from app.metrics import get_store_metrics
from app.funnel import get_store_funnel

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup — create tables then pre-load POS data
    init_db()
    db = SessionLocal()
    try:
        from app.pos_matcher import load_and_match_pos
        load_and_match_pos(db)
    finally:
        db.close()
    yield
    # (shutdown logic goes here if ever needed)

from app.logging_config import setup_logging

app = FastAPI(title="Store Intelligence API", lifespan=lifespan)
setup_logging(app)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    trace_id = request.headers.get("X-Trace-Id", "unavailable")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": "Database is temporarily unavailable.",
                "trace_id": trace_id,
            }
        },
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    trace_id = request.headers.get("X-Trace-Id", "unavailable")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "trace_id": trace_id,
            }
        },
    )

@app.get("/")
def root():
    return {"message": "Store Intelligence API"}

@app.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    from app.health import get_health_status
    return get_health_status(db)

@app.post("/events/ingest", response_model=IngestResponse)
async def ingest_events(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    return process_ingestion(payload, db)

@app.get("/stores/{store_id}/metrics", response_model=MetricsResponse)
def get_metrics(store_id: str, db: Session = Depends(get_db)):
    return get_store_metrics(store_id, db)

@app.get("/stores/{store_id}/funnel", response_model=FunnelResponse)
def get_funnel(store_id: str, db: Session = Depends(get_db)):
    return get_store_funnel(store_id, db)

@app.get("/stores/{store_id}/heatmap", response_model=HeatmapResponse)
def get_heatmap(store_id: str, db: Session = Depends(get_db)):
    from app.heatmap import get_store_heatmap
    return get_store_heatmap(store_id, db)

@app.get("/stores/{store_id}/anomalies", response_model=AnomaliesResponse)
def get_anomalies(store_id: str, db: Session = Depends(get_db)):
    from app.anomalies import get_store_anomalies
    return get_store_anomalies(store_id, db)
