import urllib.request
import json

data = b'{"events":[{"event_id":"550e8400-e29b-41d4-a716-446655440000","store_id":"STORE_BLR_002","camera_id":"CAM_ENTRY_01","visitor_id":"VIS_001","event_type":"ENTRY","timestamp":"2026-03-03T14:22:10Z","zone_id":null,"dwell_ms":0,"is_staff":false,"confidence":0.91,"metadata":{"queue_depth":null,"sku_zone":null,"session_seq":1}}]}'

req = urllib.request.Request('http://localhost:8000/events/ingest', data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as res:
        print("Status:", res.status)
        print("Response:", res.read().decode())
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print(e.read().decode())
