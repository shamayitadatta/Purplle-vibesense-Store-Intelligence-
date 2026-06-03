#!/usr/bin/env bash
set -e

echo "Checking health..."
curl -s http://localhost:8000/health | grep -q "status"

echo "Checking metrics..."
curl -s http://localhost:8000/stores/STORE_BLR_002/metrics | grep -q "store_id"

echo "Checking docs..."
test -f docs/DESIGN.md
test -f docs/CHOICES.md

echo "Acceptance checks passed."
