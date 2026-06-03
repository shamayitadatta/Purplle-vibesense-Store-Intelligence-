#!/usr/bin/env sh
set -eu

python pipeline/detect.py \
  --clips-dir "${CLIPS_DIR:-data/cctv_footage}" \
  --layout "${LAYOUT_PATH:-data/store_layout.json}" \
  --pos-data "${POS_DATA_PATH:-data/files/Brigade_Bangalore_10_April_26.csv}" \
  --output "${EVENTS_OUTPUT:-data/events.jsonl}"
