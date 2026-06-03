"""
Seed script: generates realistic visitor events for STORE_BLR_002 and
posts them to the API in batches of 100.

Run order:
  1. Waits until GET /health returns HTTP 200 (retries every 2 s, up to 60 s).
    2. Skips seeding if the store already has events (unless SEED_FORCE=1).
    3. Sends all events via POST /events/ingest.
    4. Exits 0 on success, 1 on failure.
"""

import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ── Configuration ─────────────────────────────────────────────────────────────
API_BASE = os.getenv("API_BASE", "http://api:8000")
STORE_ID = os.getenv("STORE_ID", "STORE_BLR_002")
SEED_FORCE = os.getenv("SEED_FORCE", "0").strip().lower() in {"1", "true", "yes"}
CAMERAS  = ["CAM_1", "CAM_2", "CAM_3", "CAM_4", "CAM_5"]
ZONES    = ["ENTRY", "SKINCARE", "MAKEUP", "FRAGRANCE", "BILLING"]

# Base time: simulate a busy trading day (today, store opens at 10:00 UTC)
BASE_TIME = datetime.now(timezone.utc).replace(
    hour=4, minute=0, second=0, microsecond=0          # 04:00 UTC = 09:30 IST
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def ts(offset_minutes: float) -> str:
    """Return ISO-8601 timestamp offset_minutes after BASE_TIME."""
    return (BASE_TIME + timedelta(minutes=offset_minutes)).isoformat()


def ev(visitor_id: str, camera_id: str, event_type: str,
       offset_min: float, zone_id: str = None,
       dwell_ms: int = 0, is_staff: bool = False,
       confidence: float = 0.92, metadata: dict = None) -> dict:
    
    event_id = str(uuid.uuid4())

    return {
        "event_id":   event_id,
        "store_id":   STORE_ID,
        "camera_id":  camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp":  ts(offset_min),
        "zone_id":    zone_id,
        "dwell_ms":   dwell_ms,
        "is_staff":   is_staff,
        "confidence": confidence,
        "metadata":   metadata or {},
    }


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def wait_for_api(max_wait_s: int = 90) -> None:
    url     = f"{API_BASE}/health"
    deadline = time.time() + max_wait_s
    print(f"[seeder] Waiting for API at {url} …", flush=True)
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    print("[seeder] API is up!", flush=True)
                    return
        except Exception:
            pass
        time.sleep(2)
    print(f"[seeder] ERROR: API did not become ready within {max_wait_s}s.", flush=True)
    sys.exit(1)


def should_seed() -> bool:
    if SEED_FORCE:
        print("[seeder] SEED_FORCE=1 set; seeding regardless of existing data.", flush=True)
        return True
    url = f"{API_BASE}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        last_event = data.get("last_event_timestamp_per_store", {})
        if STORE_ID in last_event:
            print(
                f"[seeder] Found existing events for {STORE_ID} "
                f"(last at {last_event[STORE_ID]}). Skipping seed.",
                flush=True,
            )
            return False
    except Exception as exc:
        print(
            f"[seeder] WARN: Could not check existing events ({exc}); proceeding to seed.",
            flush=True,
        )
    return True


def send_in_batches(events: list, batch_size: int = 100) -> None:
    url   = f"{API_BASE}/events/ingest"
    total = len(events)
    sent  = 0
    for i in range(0, total, batch_size):
        batch   = events[i : i + batch_size]
        payload = {"events": batch}
        result  = post_json(url, payload)
        sent   += result.get("accepted", 0)
        dups    = result.get("duplicates", 0)
        errs    = result.get("rejected", 0)
        print(
            f"[seeder] Batch {i // batch_size + 1}: "
            f"accepted={result.get('accepted',0)}  "
            f"duplicates={dups}  rejected={errs}",
            flush=True,
        )
    print(f"[seeder] Done — {sent}/{total} events accepted.", flush=True)


# ── Event generation ───────────────────────────────────────────────────────────

def build_events() -> list:
    events = []

    # ------------------------------------------------------------------
    # 40 unique shoppers across a 6-hour window
    # Each visitor follows a realistic path through the store zones.
    # ------------------------------------------------------------------
    visitor_paths = [
        # (visitor_id, arrival_offset_min, zones_visited, converts, staff)
        # Early morning shoppers
        ("VIS_001", 2,  ["SKINCARE", "MAKEUP"],         True,  False),
        ("VIS_002", 5,  ["MAKEUP", "FRAGRANCE"],         True,  False),
        ("VIS_003", 8,  ["SKINCARE"],                    False, False),
        ("VIS_004", 12, ["FRAGRANCE", "BILLING"],        True,  False),
        ("VIS_005", 15, ["MAKEUP"],                      False, False),
        # Mid-morning wave
        ("VIS_006", 20, ["SKINCARE", "MAKEUP", "BILLING"], True, False),
        ("VIS_007", 22, ["FRAGRANCE"],                   False, False),
        ("VIS_008", 25, ["SKINCARE", "FRAGRANCE"],       True,  False),
        ("VIS_009", 28, ["MAKEUP", "BILLING"],           True,  False),
        ("VIS_010", 30, ["SKINCARE"],                    False, False),
        # Staff members (should NOT count as visitors)
        ("STF_001", 0,  ["SKINCARE", "MAKEUP", "BILLING"], False, True),
        ("STF_002", 1,  ["FRAGRANCE", "BILLING"],           False, True),
        # Lunch rush
        ("VIS_011", 35, ["MAKEUP", "SKINCARE"],           True,  False),
        ("VIS_012", 37, ["SKINCARE", "BILLING"],          True,  False),
        ("VIS_013", 40, ["FRAGRANCE"],                    False, False),
        ("VIS_014", 42, ["MAKEUP"],                       False, False),
        ("VIS_015", 44, ["SKINCARE", "MAKEUP", "FRAGRANCE", "BILLING"], True, False),
        ("VIS_016", 46, ["SKINCARE"],                     False, False),
        ("VIS_017", 48, ["MAKEUP", "FRAGRANCE"],          True,  False),
        ("VIS_018", 50, ["BILLING"],                      True,  False),
        # Afternoon visitors
        ("VIS_019", 60, ["SKINCARE"],                     False, False),
        ("VIS_020", 63, ["MAKEUP", "SKINCARE"],           True,  False),
        ("VIS_021", 66, ["FRAGRANCE", "BILLING"],         True,  False),
        ("VIS_022", 70, ["SKINCARE", "BILLING"],          True,  False),
        ("VIS_023", 73, ["MAKEUP"],                       False, False),
        ("VIS_024", 75, ["FRAGRANCE"],                    False, False),
        ("VIS_025", 78, ["SKINCARE", "MAKEUP"],           True,  False),
        ("VIS_026", 80, ["BILLING"],                      True,  False),
        # Queue abandonment scenarios
        ("VIS_027", 85, ["SKINCARE", "BILLING"],          False, False),  # abandons queue
        ("VIS_028", 87, ["MAKEUP", "BILLING"],            False, False),  # abandons queue
        # Re-entry visitor
        ("VIS_029", 90, ["SKINCARE"],                     False, False),
        ("VIS_029", 95, ["MAKEUP", "BILLING"],            True,  False),  # re-enters
        # Evening rush
        ("VIS_030", 100, ["SKINCARE", "MAKEUP", "BILLING"], True, False),
        ("VIS_031", 102, ["FRAGRANCE", "BILLING"],           True, False),
        ("VIS_032", 104, ["SKINCARE"],                       False, False),
        ("VIS_033", 106, ["MAKEUP"],                         False, False),
        ("VIS_034", 108, ["FRAGRANCE", "SKINCARE", "BILLING"], True, False),
        ("VIS_035", 110, ["MAKEUP", "FRAGRANCE"],             True, False),
        ("VIS_036", 112, ["SKINCARE", "BILLING"],             True, False),
        ("VIS_037", 114, ["FRAGRANCE"],                       False, False),
        ("VIS_038", 116, ["MAKEUP", "BILLING"],               True, False),
    ]

    abandoners = {"VIS_027", "VIS_028"}   # these visitors abandon the billing queue

    cam_idx = 0
    for (visitor_id, arrival, zones, converts, is_staff) in visitor_paths:
        cam = CAMERAS[cam_idx % len(CAMERAS)]
        cam_idx += 1

        # Determine event type for the entry (REENTRY if visitor already appeared)
        entry_type = "ENTRY"
        for prev_vid, prev_arr, *_ in visitor_paths:
            if prev_vid == visitor_id and prev_arr < arrival:
                entry_type = "REENTRY"
                break

        # ENTRY / REENTRY
        events.append(ev(visitor_id, cam, entry_type, arrival,
                         zone_id="ENTRY", dwell_ms=0,
                         is_staff=is_staff))

        offset = arrival + 1

        # Walk through zones
        for zone in zones:
            dwell = 90_000 if zone == "SKINCARE" \
                else 75_000 if zone == "MAKEUP" \
                else 60_000 if zone == "FRAGRANCE" \
                else 30_000  # BILLING

            events.append(ev(visitor_id, cam, "ZONE_ENTER", offset,
                             zone_id=zone, dwell_ms=0, is_staff=is_staff))
            offset += 0.5

            events.append(ev(visitor_id, cam, "ZONE_DWELL", offset,
                             zone_id=zone, dwell_ms=dwell, is_staff=is_staff))
            offset += dwell / 60_000      # convert ms → minutes

            events.append(ev(visitor_id, cam, "ZONE_EXIT", offset,
                             zone_id=zone, dwell_ms=0, is_staff=is_staff))
            offset += 0.5

        # Billing queue logic
        if "BILLING" in zones and not is_staff:
            queue_depth = 2
            events.append(ev(visitor_id, cam, "BILLING_QUEUE_JOIN", offset,
                             zone_id="BILLING", dwell_ms=0,
                             metadata={"queue_depth": queue_depth}))
            offset += 1

            if visitor_id in abandoners:
                events.append(ev(visitor_id, cam, "BILLING_QUEUE_ABANDON", offset,
                                 zone_id="BILLING", dwell_ms=0,
                                 metadata={"queue_depth": queue_depth}))
                offset += 0.5

        # EXIT
        events.append(ev(visitor_id, cam, "EXIT", offset,
                         zone_id=None, dwell_ms=0, is_staff=is_staff))

    print(f"[seeder] Built {len(events)} events for store {STORE_ID}.", flush=True)
    return events


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    wait_for_api()
    if not should_seed():
        sys.exit(0)
    events = build_events()
    send_in_batches(events)
