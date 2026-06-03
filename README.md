# Store Intelligence API

## 1. What this project does
The Store Intelligence system processes raw anonymized CCTV footage to generate a structured event stream (entries, exits, zone dwells, and billing queues). These events are ingested by a FastAPI backend, which aggregates them into live analytics such as unique visitor counts, conversion rates, zone heatmaps, and funnel drop-offs. The analytics are surfaced via a real-time React + Vite dashboard.

## 2. Tech stack
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy, SQLite
- **Detection Pipeline**: Python, OpenCV, Ultralytics (YOLOv8), ByteTrack
- **Frontend Dashboard**: React, Vite, TypeScript, Tailwind CSS, Recharts
- **DevOps**: Docker, Docker Compose, Pytest

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     store.mp4 / CCTV Feed                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ Frame stream (OpenCV)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                app.py — Detection Pipeline              │
│                                                             │
│   ┌─────────────┐    ┌──────────────┐    ┌──────────────┐   │
│   │  YOLOv8n    │───▶│  ByteTrack   │───▶│ Zone Mapper  │   │
│   │  Detection  │    │  Re-ID +     │    │ Entry/Exit   │   │
│   │  ~28ms/frame│    │  Tracking    │    │ Direction    │   │
│   └─────────────┘    └──────────────┘    └──────┬───────┘   │
└──────────────────────────────────────────────────┼──────────┘
                                                   │
                  ┌────────────────────────────────▼─────────┐
                  │      vibe_engine.py — Shared Metrics     │
                  │  store_metrics dict (thread-safe)        │
                  │  current_count · vibe · music · alerts   │
                  └────────────────────────────────┬─────────┘
                                                   │
              ┌────────────────────────────────────▼─────────┐
              │          main.py — FastAPI Backend           │
              │                                              │
              │  GET  /                    → Dashboard       │
              │  GET  /api/v1/store/vibe   → Live metrics    │
              │  POST /api/v1/ai/insights  → AI analysis     │
              │  POST /events/ingest       → Event pipeline  │
              │  GET  /stores/{id}/...     → Analytics API   │
              └────────────────────────────────────┬─────────┘
                                                   │
              ┌────────────────────────────────────▼─────────┐
              │     templates/index.html — Live Dashboard    │
              │  KPIs · Charts · Heatmap · Alerts · Export   │
              └──────────────────────────────────────────────┘
```

---

```

## 4. Quick start
Clone and run — one command is all you need:
```bash
git clone <repo-url>
cd store-intelligence
docker compose up
```

That's it. `docker compose up` automatically:
1. **Builds** both Docker images (API + Dashboard) on first run
2. **Starts** the FastAPI backend on port 8000
3. **Starts** the React dashboard on port 5173
4. **Creates** the SQLite database

It also runs a one-shot **seeder** that posts demo events after the API is healthy.
If data already exists for `STORE_BLR_002`, the seeder skips automatically.
To force a re-seed, delete `./data/store_intelligence.db` or run:
```bash
SEED_FORCE=1 docker compose up
```

No `--build` flag needed. No `.env` file needed (all environment variables have defaults in `docker-compose.yml`).

After Compose starts:
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Dashboard: `http://localhost:5173`
- Health: `http://localhost:8000/health`

> **Optional:** Copy `.env.example` to `.env` if you want to customise configuration:
> ```bash
> cp .env.example .env
> ```

## 5. Run detection pipeline
The challenge CCTV files should live in `data/cctv_footage/`. To process videos and generate events, run:
```bash
python pipeline/detect.py \
  --clips-dir data/cctv_footage \
  --layout data/store_layout.json \
  --pos-data data/files/Brigade_Bangalore_10_April_26.csv \
  --output data/events.jsonl
```

The POS CSV in `data/files/` is used to align generated event timestamps and calculate POS-matched conversion rate. The layout workbook is retained as the source reference; the runnable polygon config is in `data/store_layout.json`.

## 6. Replay events into API
To batch ingest the generated events into the API, run:
```bash
python pipeline/replay_events.py \
  --file data/events.jsonl \
  --api http://localhost:8000/events/ingest
```

## 7. API endpoints
- `POST /events/ingest` - Accepts batch JSON events
- `GET /stores/{id}/metrics` - Top-line store metrics
- `GET /stores/{id}/funnel` - Session-based conversion funnel
- `GET /stores/{id}/heatmap` - Zone performance heatmap
- `GET /stores/{id}/anomalies` - Active operational anomalies
- `GET /health` - System health and stale feed warnings

## 8. Run tests
Tests are written in Pytest with a minimum 70% coverage requirement.
```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
pytest --cov=app --cov=pipeline --cov-report=term-missing
```

The Docker API image intentionally installs only `requirements-api.txt`. The heavier YOLO/OpenCV stack lives in `requirements-pipeline.txt`, and test-only tools live in `requirements-dev.txt`.

## 9. Dashboard
The dashboard provides a real-time visual interface to the API. To run it locally:
```bash
cd dashboard
npm ci
npm run dev
```
Open `http://localhost:5173` in your browser.
**Live Demo →** [purplle-vibesense.onrender.com](https://purplle-vibesense.onrender.com)  
**API Docs →** [purplle-vibesense.onrender.com/docs](https://purplle-vibesense.onrender.com/docs)

### 1. Detection Model — YOLOv8n

| Model | Latency | mAP | Size | Decision |
|-------|---------|-----|------|----------|
| YOLOv8n | ~28ms | 37.3 | 6.3MB | ✅ Chosen |
| YOLOv8s | ~45ms | 44.9 | 22MB | Too slow for real-time |
| Faster R-CNN | ~120ms | 46.2 | 140MB | Not streaming-viable |
| MobileNet-SSD | ~20ms | 23.1 | 6.9MB | Accuracy insufficient |

**Trade-off:** YOLOv8n loses ~7 mAP vs YOLOv8s but gains 40% latency reduction — critical for
real-time retail analytics.

### 2. Tracking — ByteTrack over DeepSORT

ByteTrack uses IoU-based matching + Kalman filter prediction with **no extra Re-ID network**.
DeepSORT requires a separate appearance model (+50–80ms). ByteTrack gives comparable tracking
accuracy with zero added inference cost — a deliberate production trade-off.

### 3. Concurrency — Background Thread + Shared Dict

The detection pipeline runs as a daemon thread. `store_metrics` is a shared Python dict updated
by the pipeline and read by FastAPI handlers. For production scale: replace with Redis pub/sub.
Current design is intentionally simple and observable.

### 4. Vibe Engine — Rule-based Weighted Scoring

```python
vibe_score = (
    occupancy_ratio    * 0.40 +   # Store fullness
    zone_activity      * 0.35 +   # Which zones are active
    dwell_time_score   * 0.25     # Lingering vs rushing
)
```

No ML model for vibe — deliberate choice. No labeled training data exists for "store vibe."
Rule-based is explainable, tunable, and immediately deployable.

### 5. Frontend — Single HTML File

The entire dashboard (`templates/index.html`) is a single self-contained file with zero build
step. Chart.js loaded via CDN. Deployable anywhere, zero Node.js dependency, instant iteration.
Trade-off: harder to maintain at scale.

---

## 📡 API Reference

Full interactive docs at **[/docs](https://purplle-vibesense.onrender.com/docs)**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Feed status, uptime, anomaly flag |
| `GET` | `/api/v1/store/vibe` | Live occupancy, vibe, music, alerts |
| `POST` | `/api/v1/ai/insights` | Claude-powered store recommendations |
| `POST` | `/events/ingest` | Idempotent event ingest (dedup by event_id) |
| `GET` | `/stores/{id}/metrics` | Unique visitors, conversion rate, dwell per zone |
| `GET` | `/stores/{id}/funnel` | Entry → Zone Visit → Billing Queue → Purchase |
| `GET` | `/stores/{id}/heatmap` | Zone traffic normalised 0–100 with confidence |
| `GET` | `/stores/{id}/anomalies` | Active anomalies with severity + suggested action |
| `GET` | `/stores/{id}/events` | Raw event log with limit pagination |
| `GET` | `/stores/{id}/zones` | Zone occupancy and avg dwell seconds |

### Example — `GET /api/v1/store/vibe`

```json
{
  "current_occupancy": 7,
  "store_vibe": "Cozy & Premium",
  "ambient_music": "Soft acoustic melodies playing.",
  "realtime_alerts": [
    "💡 Floor Alert: High linger-duration observed near aisle 3."
  ]
}
```

### Example — `POST /events/ingest`

```json
[
  {
    "event_id": "uuid-here",
    "store_id": "STORE_001",
    "camera_id": "CAM_ENTRY_01",
    "visitor_id": "VIS_abc123",
    "event_type": "ENTRY",
    "timestamp": "2026-05-31T10:00:00+00:00",
    "zone_id": null,
    "dwell_ms": 0,
    "is_staff": false,
    "confidence": 0.95,
    "metadata": {}
  }
]
```

Response:
```json
{
  "status": "success",
  "inserted": 1,
  "duplicates": 0,
  "errors": [],
  "total_events": 1
}
```

### Example — `GET /stores/{id}/anomalies`

```json
{
  "store_id": "STORE_001",
  "active_anomalies": [
    {
      "anomaly_type": "CONVERSION_DROP",
      "severity": "WARN",
      "description": "Conversion 8.3% below 25% baseline. 12 visitors, 1 reached billing.",
      "suggested_action": "Deploy floor staff to guide customers to billing.",
      "value": 0.0833
    }
  ],
  "checked_at": "2026-05-31T18:24:28+00:00"
}
```

---

## 🧪 Tests

```bash
pytest test_main.py -v
```

**33 tests · 9 endpoints · zero state leakage between tests**

| Class | Tests | What It Covers |
|-------|-------|----------------|
| `TestHealth` | 4 | Feed status transitions, response shape |
| `TestStoreVibe` | 2 | Live vibe fields |
| `TestIngest` | 5 | Idempotency, batch, accumulation |
| `TestMetrics` | 7 | Staff exclusion, zero traffic, dwell, store isolation |
| `TestFunnel` | 5 | Re-entry dedup, stage order, dropoff never negative |
| `TestHeatmap` | 4 | Normalisation, sort order, confidence flag |
| `TestAnomalies` | 5 | Conversion drop, dead zone, severity values |
| `TestStoreEvents` | 3 | Pagination, isolation |
| `TestZones` | 4 | Occupancy count, staff exclusion, dwell calc |
| `TestAIInsights` | 3 | Missing key → 500, bad shape → 422, live skip |

Key edge cases covered:
- **Idempotency** — same event_id sent twice → second call returns `inserted: 0, duplicates: 1`
- **Staff exclusion** — `is_staff=True` events never count as unique visitors
- **Re-entry dedup** — `REENTRY` event type never inflates funnel ENTRY count
- **Store isolation** — events for STORE_A never appear in STORE_B metrics
- **Zero traffic** — all endpoints return valid zero-state, never crash

---

## 🚨 Anomaly Detection

| Anomaly | Trigger | Severity |
|---------|---------|----------|
| `CAPACITY_EXCEEDED` | Occupancy > store threshold | CRITICAL |
| `BILLING_QUEUE_SPIKE` | Queue depth ≥ 8 in last 5 min | CRITICAL |
| `CONVERSION_DROP` | Conversion < 25% with 10+ visitors | WARN |
| `BILLING_QUEUE_SPIKE` | Queue depth 5–7 in last 5 min | WARN |
| `DEAD_ZONE` | Zone with no visits in last 30 min | INFO |

Each anomaly includes a `suggested_action` string for floor staff.

---

## 🎵 Ambient Music Intelligence

| Vibe | Occupancy | Music |
|------|-----------|-------|
| Cozy & Premium | < 40% capacity | Soft acoustic · BPM 60–80 |
| Moderate & Buzzing | 40–75% capacity | Lo-fi indie · BPM 80–100 |
| Energetic & Crowded | > 75% capacity | Upbeat synth-pop · BPM 100–130 |

Transitions use 30-second hysteresis to prevent boundary flickering.

---

## ⚠️ Known Limitations & Production Path

| Limitation | Root Cause | Production Fix |
|------------|------------|----------------|
| Simulated zone coordinates | No camera calibration | Homography mapping from store layout |
| In-memory event store | Simplicity | PostgreSQL + event log |
| In-memory metrics | Simplicity | Redis pub/sub |
| Single camera | One video source | Multi-camera + cross-camera Re-ID |
| Cold start delay | Render free tier | Paid tier / Railway |
| Naive timestamps in AI pipeline | `datetime.utcnow()` legacy | Fixed — `datetime.now(timezone.utc)` |

---


