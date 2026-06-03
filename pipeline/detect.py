import argparse
import cv2
from ultralytics import YOLO
import sys
import os
import json
from datetime import datetime, timezone, timedelta

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pipeline.state import VisitorStateTracker
from pipeline.zones import get_zone_for_point, bbox_center, load_store_layout
from app.pos_matcher import infer_first_pos_timestamp

DEFAULT_CLIPS_DIR = "data/cctv_footage"
DEFAULT_LAYOUT_PATH = "data/store_layout.json"
DEFAULT_EVENTS_OUTPUT = "data/events.jsonl"
DEFAULT_POS_PATH = "data/files/Brigade_Bangalore_10_April_26.csv"


def camera_id_from_filename(filename):
    stem = os.path.splitext(filename)[0]
    return stem.strip().upper().replace(" ", "_").replace("-", "_")


def parse_base_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def infer_base_time(base_time_arg, pos_data_path):
    explicit = parse_base_time(base_time_arg)
    if explicit:
        return explicit

    pos_ts = infer_first_pos_timestamp(pos_data_path)
    if pos_ts:
        if pos_ts.tzinfo is None:
            pos_ts = pos_ts.replace(tzinfo=timezone.utc)
        return pos_ts - timedelta(minutes=5)

    return datetime.now(timezone.utc)

def main():
    parser = argparse.ArgumentParser(description="Full YOLO Detection Pipeline")
    parser.add_argument("--clips-dir", default=DEFAULT_CLIPS_DIR, help="Path to CCTV footage directory")
    parser.add_argument("--layout", default=DEFAULT_LAYOUT_PATH, help="Path to store layout JSON")
    parser.add_argument("--output", default=DEFAULT_EVENTS_OUTPUT, help="Path to output events.jsonl")
    parser.add_argument("--pos-data", default=DEFAULT_POS_PATH, help="Optional POS CSV used to align event timestamps")
    parser.add_argument("--base-time", default=os.getenv("CCTV_BASE_TIME"), help="Optional ISO timestamp for the first clip")
    args = parser.parse_args()

    layout = load_store_layout(args.layout)
    if not layout or not layout.get("stores"):
        print("Error: Invalid or empty layout file.")
        sys.exit(1)
        
    store = layout["stores"][0]
    store_id = store.get("store_id", "STORE_BLR_002")
    camera_id = "CAM_ENTRY_01"
    if store.get("cameras"):
        camera_id = store["cameras"][0].get("camera_id", camera_id)

    print("Loading YOLOv8n model...")
    model = YOLO("yolov8n.pt")

    if not os.path.exists(args.clips_dir):
        print(f"Error: Clips directory {args.clips_dir} not found")
        sys.exit(1)

    tracker_state = VisitorStateTracker(store_id, camera_id)
    events_generated = []
    visitor_seq = 0
    clip_base_time = infer_base_time(args.base_time, args.pos_data)

    # Process each video in the directory
    for clip_index, filename in enumerate(sorted(os.listdir(args.clips_dir))):
        if not filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
            continue
            
        video_path = os.path.join(args.clips_dir, filename)
        camera_id = camera_id_from_filename(filename) or tracker_state.camera_id
        tracker_state.camera_id = camera_id
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video {video_path}")
            continue

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0
            
        frame_idx = 0
        track_to_visitor = {}
        base_time = clip_base_time + timedelta(minutes=clip_index * 20)

        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_idx += 1
            
            # Process every 5th frame for speed
            if frame_idx % 5 != 0:
                continue
                
            # Current simulated timestamp based on frame index
            current_time = base_time + timedelta(seconds=frame_idx / fps)
            
            # Default entry line across the middle of the frame if not specified
            h, w = frame.shape[:2]
            entry_line = [(0, h // 2), (w, h // 2)]
                
            results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
            
            for r in results:
                if r.boxes is not None and r.boxes.id is not None:
                    for box, track_id_tensor in zip(r.boxes, r.boxes.id):
                        cls_id = int(box.cls[0])
                        if cls_id == 0:  # person
                            track_id = int(track_id_tensor.item())
                            xyxy = box.xyxy[0].tolist()
                            confidence = float(box.conf[0])
                            
                            if track_id not in track_to_visitor:
                                visitor_seq += 1
                                track_to_visitor[track_id] = f"VIS_{camera_id}_{visitor_seq:06d}"
                                
                            visitor_id = track_to_visitor[track_id]
                            
                            point = bbox_center(xyxy)
                            
                            # 1. Update Position (generates ENTRY/EXIT)
                            pos_events = tracker_state.update_position(visitor_id, point, current_time, entry_line, confidence=confidence)
                            events_generated.extend(pos_events)
                            
                            # 2. Update Zone (generates ZONE_ENTER/ZONE_EXIT/ZONE_DWELL/BILLING)
                            zone = get_zone_for_point(store_id, camera_id, point, layout_path=args.layout)
                            zone_events = tracker_state.update_zone(visitor_id, zone, current_time, confidence=confidence)
                            events_generated.extend(zone_events)
                            
        cap.release()

    # Save to output file
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        for ev in events_generated:
            # We need to serialize datetime correctly if make_event returned dicts with datetime objects
            # wait, make_event from pipeline.emit usually serializes it, let's check.
            # Assuming make_event returns a dict that is json serializable
            # wait, make_event returns a dict. We must ensure datetime is string.
            if "timestamp" in ev and isinstance(ev["timestamp"], datetime):
                ev["timestamp"] = ev["timestamp"].isoformat().replace('+00:00', 'Z')
            f.write(json.dumps(ev) + "\n")
            
    print(f"Processing complete. Generated {len(events_generated)} events.")

if __name__ == "__main__":
    main()
