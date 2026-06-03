import csv
import json
import os
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db_models import EventDB, PosTransactionDB

DEFAULT_POS_PATH = "data/files/Brigade_Bangalore_10_April_26.csv"
FALLBACK_POS_PATH = "data/pos_transactions.csv"
DEFAULT_LAYOUT_PATH = "data/store_layout.json"


def _candidate_pos_paths(csv_path=None):
    if csv_path:
        return [csv_path]

    env_path = os.getenv("POS_DATA_PATH")
    paths = [env_path, DEFAULT_POS_PATH, FALLBACK_POS_PATH]
    return [path for path in paths if path]


def _layout_store_aliases(layout_path=DEFAULT_LAYOUT_PATH):
    aliases = {}
    default_store_id = "STORE_BLR_002"

    if not os.path.exists(layout_path):
        return aliases, default_store_id

    try:
        with open(layout_path, "r", encoding="utf-8") as f:
            layout = json.load(f)
    except (json.JSONDecodeError, OSError):
        return aliases, default_store_id

    stores = layout.get("stores", [])
    if stores:
        default_store_id = stores[0].get("store_id", default_store_id)

    for store in stores:
        canonical = store.get("store_id")
        if not canonical:
            continue
        for key in ("store_id", "source_store_id", "store_name"):
            value = store.get(key)
            if value:
                aliases[str(value).strip().lower()] = canonical

    return aliases, default_store_id


def _normalize_store_id(raw_store_id, raw_store_name=None):
    aliases, default_store_id = _layout_store_aliases()

    for value in (raw_store_id, raw_store_name):
        if not value:
            continue
        normalized = aliases.get(str(value).strip().lower())
        if normalized:
            return normalized

    if raw_store_id and str(raw_store_id).startswith("STORE_"):
        return str(raw_store_id)

    return default_store_id


def _parse_timestamp(row):
    timestamp = row.get("timestamp")
    if timestamp:
        candidates = [timestamp]
    else:
        date_part = row.get("order_date") or row.get("date")
        time_part = row.get("order_time") or row.get("time") or "00:00:00"
        candidates = [f"{date_part} {time_part}" if date_part else ""]

    formats = [
        None,
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for value in candidates:
        if not value:
            continue
        cleaned = str(value).strip().replace("Z", "+00:00")
        for fmt in formats:
            try:
                if fmt is None:
                    parsed = datetime.fromisoformat(cleaned)
                else:
                    parsed = datetime.strptime(cleaned, fmt)
                return parsed.replace(tzinfo=None)
            except ValueError:
                continue

    return None


def _parse_float(value):
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0


def _transaction_from_row(row):
    invoice_type = str(row.get("invoice_type") or "sales").strip().lower()
    if invoice_type and invoice_type not in {"sales", "sale"}:
        return None

    tx_id = row.get("transaction_id") or row.get("order_id") or row.get("invoice_number")
    tx_ts = _parse_timestamp(row)
    if not tx_id or not tx_ts:
        return None

    basket_value = (
        row.get("basket_value_inr")
        or row.get("total_amount")
        or row.get("NMV")
        or row.get("GMV")
        or row.get("taxable_amt")
    )

    return {
        "transaction_id": str(tx_id),
        "store_id": _normalize_store_id(row.get("store_id"), row.get("store_name")),
        "timestamp": tx_ts,
        "basket_value_inr": _parse_float(basket_value),
    }


def _read_transactions(csv_path):
    grouped = {}

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx = _transaction_from_row(row)
            if not tx:
                continue

            key = tx["transaction_id"]
            if key not in grouped:
                grouped[key] = tx
            else:
                grouped[key]["basket_value_inr"] += tx["basket_value_inr"]
                if tx["timestamp"] < grouped[key]["timestamp"]:
                    grouped[key]["timestamp"] = tx["timestamp"]

    return grouped.values()


def infer_first_pos_timestamp(csv_path=DEFAULT_POS_PATH):
    if not csv_path or not os.path.exists(csv_path):
        return None

    timestamps = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed = _parse_timestamp(row)
            if parsed:
                timestamps.append(parsed)

    return min(timestamps) if timestamps else None


def load_and_match_pos(db: Session, csv_path: str = None):
    for path in _candidate_pos_paths(csv_path):
        if not os.path.exists(path):
            continue

        for tx_data in _read_transactions(path):
            tx_id = tx_data["transaction_id"]
            existing = db.query(PosTransactionDB).filter(PosTransactionDB.transaction_id == tx_id).first()
            if existing:
                continue

            tx_ts = tx_data["timestamp"]
            tx = PosTransactionDB(
                transaction_id=tx_id,
                store_id=tx_data["store_id"],
                timestamp=tx_ts,
                basket_value_inr=tx_data["basket_value_inr"],
                matched_visitor_id=None,
            )

            window_start = tx_ts - timedelta(minutes=5)
            candidates = db.query(EventDB).filter(
                EventDB.store_id == tx.store_id,
                EventDB.timestamp >= window_start,
                EventDB.timestamp <= tx_ts,
                EventDB.is_staff == False,
                EventDB.event_type.in_(["BILLING_QUEUE_JOIN", "ZONE_ENTER", "ZONE_DWELL"]),
            ).all()

            valid_candidates = []
            for candidate in candidates:
                if candidate.event_type == "BILLING_QUEUE_JOIN":
                    valid_candidates.append(candidate)
                elif candidate.zone_id and "billing" in candidate.zone_id.lower():
                    valid_candidates.append(candidate)

            if valid_candidates:
                best_candidate = max(valid_candidates, key=lambda event: event.timestamp)
                tx.matched_visitor_id = best_candidate.visitor_id

            db.add(tx)

        db.commit()
        return


def calculate_conversion_rate(store_id: str, db: Session) -> float:
    unique_visitors = db.query(func.count(func.distinct(EventDB.visitor_id)))\
        .filter(EventDB.store_id == store_id)\
        .filter(EventDB.event_type.in_(["ENTRY", "REENTRY"]))\
        .filter(EventDB.is_staff == False)\
        .scalar() or 0

    if unique_visitors == 0:
        return 0.0

    converted = db.query(func.count(func.distinct(PosTransactionDB.matched_visitor_id)))\
        .filter(PosTransactionDB.store_id == store_id)\
        .filter(PosTransactionDB.matched_visitor_id.isnot(None))\
        .scalar() or 0

    return converted / unique_visitors
