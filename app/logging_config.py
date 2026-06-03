import time
import uuid
import json
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Configure basic logging
logger = logging.getLogger("store_intelligence")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
# For JSON formatting, we can just log a JSON string.
handler.setFormatter(logging.Formatter('%(message)s'))
if not logger.handlers:
    logger.addHandler(handler)

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        # Extract store_id from path if available
        store_id = None
        path_parts = request.url.path.split("/")
        if len(path_parts) >= 3 and path_parts[1] == "stores":
            store_id = path_parts[2]
            
        event_count = 0
        
        # To get event_count from /events/ingest, we must read the body.
        # But reading the body consumes it. 
        # A common trick in Starlette is to read it, then reset it.
        if request.url.path == "/events/ingest" and request.method == "POST":
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    if isinstance(data, dict) and "events" in data:
                        event_count = len(data["events"])
                    elif isinstance(data, list):
                        event_count = len(data)
                        
                    # Reset the body so endpoints can use it
                    async def receive():
                        return {"type": "http.request", "body": body}
                    request._receive = receive
            except Exception:
                pass
                
        response = await call_next(request)
        
        latency_ms = max(0, int((time.time() - start_time) * 1000))
        status_code = response.status_code
        
        log_data = {
            "trace_id": trace_id,
            "store_id": store_id,
            "endpoint": request.url.path,
            "latency_ms": latency_ms,
            "event_count": event_count,
            "status_code": status_code
        }
        
        # Log as JSON string
        logger.info(json.dumps(log_data))
        
        # Inject trace_id into response header
        response.headers["X-Trace-Id"] = trace_id
        
        return response

def setup_logging(app):
    app.add_middleware(StructuredLoggingMiddleware)
