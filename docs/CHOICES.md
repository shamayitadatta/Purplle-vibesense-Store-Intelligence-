# CHOICES.md

## Decision 1: Detection Model

### Options considered
- YOLOv8
- YOLOv11
- RT-DETR
- MediaPipe

### Final Decision

I adopted a camera-responsibility architecture where each camera owns a specific business objective.

| Camera | Responsibility          |
| ------ | ----------------------- |
| CAM 3  | Entry, Exit, Re-entry   |
| CAM 1  | Skincare Engagement     |
| CAM 2  | Makeup Engagement       |
| CAM 5  | Billing Queue Analytics |

### Why This Decision

The challenge evaluates:

* Entry accuracy
* Re-entry handling
* Group handling
* Session tracking

Assigning ownership to individual cameras reduces duplicate event generation and simplifies validation.

CAM 3 became the source of truth for visitor sessions because it provides the clearest entrance view.

CAM 1 and CAM 2 focus on customer engagement through dwell analytics.

CAM 5 focuses on billing activity because it represents the strongest observable purchase-intent signal.

### Additional Engineering Decision

CAM 4 was intentionally not assigned ownership of business-critical events.

Its field of view overlaps with other cameras and introducing event ownership there would increase the risk of:

* Double counting
* Session inflation
* Ambiguous visitor attribution

### Outcome

* Reliable visitor counting
* Cleaner event generation
* Easier debugging
* Better conversion accuracy

---

## Decision 2: Event Generation Strategy

### What AI Suggested

Generate highly granular events:

* ZONE_ENTER
* ZONE_EXIT
* Path tracking
* Movement history

### Final Decision

I focused on business-level events:

* ENTRY
* EXIT
* REENTRY
* ZONE_DWELL
* BILLING_QUEUE_JOIN

### Why This Decision

Retail managers care about:

* Visitor traffic
* Engagement
* Billing intent
* Conversion

rather than raw movement coordinates.

Dwell duration proved to be a more meaningful signal of customer interest than frequent zone transitions.

### Group Entry Handling

The challenge requires multiple people entering together to be counted individually.

Each tracked person receives an independent visitor identity.

Result:

Three customers entering together generate three ENTRY events rather than one group event.

### Re-Entry Handling

The challenge specifically highlights re-entry inflation as a known retail analytics problem.

The funnel therefore operates on visitor identities rather than raw event counts.

Result:

A returning customer generates a REENTRY event rather than creating a new visitor session.

### Outcome

* Better session accuracy
* Better funnel analytics
* Lower event complexity
* Easier event validation

---

## Decision 3: Conversion and Billing Analytics

### What AI Suggested

Directly correlate every visitor with every POS transaction.

Implement:

* Purchase attribution
* Queue abandonment
* Customer-level transaction matching

### Final Decision

Revenue metrics are computed directly from POS data while billing activity is used as the strongest observable indicator of purchase intent.

### Why This Decision

The challenge dataset contains POS transactions but does not contain customer identifiers required for direct attribution.

A reliable visitor-to-transaction mapping therefore cannot be validated confidently.

### Billing Analytics Approach

CAM 5 generates:

* BILLING_QUEUE_JOIN

events.

These events represent purchase intent rather than completed purchases.


### What AI suggested
The AI suggested RT-DETR for superior accuracy and Transformer-based global context understanding, which helps in crowded retail environments, or DeepSORT if focusing purely on re-identification strength.

### What I chose
I chose YOLOv8 combined with ByteTrack.

### Why I chose it
Given the 48-hour challenge window, YOLOv8 provides the best speed-to-implementation trade-off. It is widely supported, extremely fast, and natively integrates with ByteTrack within the `ultralytics` package. This allowed me to immediately focus on the event schema logic and API correctness rather than debugging model deployment.

### Trade-offs
YOLOv8 may struggle with severe occlusions compared to Transformer-based models, and ByteTrack can lose track identities when a subject leaves the frame entirely. I mitigated the track-loss issue by implementing a rudimentary re-entry time/location heuristic.

### What I would improve with more time
With more time, I would deploy a dedicated Re-ID model (e.g., OSNet) to extract appearance embeddings for every track. This would solve identity switches across disparate camera feeds far better than my current time/location heuristic.

---

## Decision 2: Event Schema Design Rationale

### Options considered
- Coarse-grained events (only storing `SESSION_START` and `SESSION_END`)
- Highly granular frame-by-frame state dumps
- Standardized lifecycle events (`ENTRY`, `ZONE_ENTER`, `ZONE_DWELL`, `EXIT`)

### What AI suggested
The AI initially recommended a highly granular schema that dumps bounding boxes and coordinates into a timeseries database like InfluxDB for infinite replayability and spatial analytics.

### What I chose
I chose a standardized lifecycle event stream (`ENTRY`, `EXIT`, `ZONE_ENTER`, `ZONE_DWELL`, `BILLING_QUEUE_JOIN`, `BILLING_QUEUE_ABANDON`).

### Why I chose it
This schema directly aligns with the business metrics we need to compute (conversion rate, dwell time, abandonment rate). It reduces the payload size significantly compared to frame-by-frame dumps, while preserving enough data to generate heatmaps and funnels. It complies perfectly with the API ingestion validation requirements.

### Trade-offs
We lose exact spatial paths. We know which zone a person visited and for how long, but we cannot reconstruct their exact walking trajectory (e.g., stopping at a specific endcap inside the zone) without querying the raw video again.

### What I would improve with more time
I would add an `x, y` coordinate array to the `metadata` payload of `ZONE_DWELL` events to retain a compressed trajectory for more advanced spatial heatmapping.

---

## Decision 3: API Architecture Choice

### Options considered
- Flask + SQLAlchemy
- Django + Django REST Framework
- FastAPI + Pydantic

### What AI suggested
The AI suggested FastAPI due to its async capabilities and native Pydantic integration, noting that it is quickly becoming the industry standard for Python microservices.

### What I chose
FastAPI + Pydantic v2 + SQLite.

### Why I chose it
FastAPI and Pydantic provide out-of-the-box validation for our strict event schema, automatically rejecting malformed events and generating Swagger documentation. SQLite was chosen over PostgreSQL simply to ensure the project runs seamlessly in a container without requiring a heavy database orchestration setup, fulfilling the "containerisation" and "testability" constraints of the challenge.

### Trade-offs
SQLite handles concurrent reads well but struggles with concurrent writes. If multiple detection pipelines from 10+ cameras are POSTing events simultaneously, SQLite will likely lock and throw `OperationalError`s.

### What I would improve with more time
I would migrate the storage backend to PostgreSQL for concurrent writes. Furthermore, I would place a Redis queue in front of the ingestion endpoint to buffer incoming events so the API never drops a payload during traffic spikes.

### Empty Store Handling

The challenge includes periods with no visitors.

All APIs include protection against:

* Empty event streams
* Divide-by-zero conditions
* Missing traffic

The system always returns valid responses.
|  Question                                 | Answer                                                                                                                                              |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Why no cross-camera Re-ID?                | Limited camera overlap; camera ownership architecture produced more reliable business metrics with lower complexity.                                |
| Why no staff detection?                   | Reliable classification required uniforms/badges/employee registry not present in challenge assets. Schema remains future-ready through `is_staff`. |
| Why no queue abandonment?                 | Visitor-to-transaction attribution could not be validated because POS records contained no customer identifier.                                     |
| Why use dwell instead of zone enter/exit? | Dwell time is a stronger retail engagement signal and produced more stable analytics.                                                               |
| Why CAM-specific responsibilities?        | Prevents duplicate events and simplifies validation.                                                                                                |
| Why event-driven architecture?            | Decouples detection from analytics and supports replay/debugging.                                                                                   |


### Deployment

The platform is containerised using:

* Docker
* Docker Compose

The entire application starts using:

```bash
docker compose up
```

### Outcome

* Stable API behaviour
* Reliable analytics
* Minimal deployment effort
* Production-ready architecture

---

# Final Reflection

Throughout the project, AI was used to evaluate alternatives and explore architectural options. Final implementation decisions were driven by business value, data availability, maintainability and reliability.

The architecture prioritises:

1. Accurate visitor counting.
2. Reliable session tracking.
3. Meaningful engagement analytics.
4. Practical deployment.
5. Trustworthy business metrics.

Rather than maximising feature count, the solution focuses on generating reliable retail intelligence from the available data while maintaining a clean and scalable architecture.
