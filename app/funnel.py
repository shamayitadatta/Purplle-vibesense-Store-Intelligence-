from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db_models import EventDB, PosTransactionDB
from app.models import FunnelResponse, DropoffDetails

def get_store_funnel(store_id: str, db: Session) -> FunnelResponse:
    # 1. Entry stage
    entry_count = db.query(func.count(func.distinct(EventDB.visitor_id)))\
        .filter(EventDB.store_id == store_id)\
        .filter(EventDB.event_type.in_(["ENTRY", "REENTRY"]))\
        .filter(EventDB.is_staff == False).scalar() or 0

    # 2. Zone visit stage
    zone_visit_count = db.query(func.count(func.distinct(EventDB.visitor_id)))\
        .filter(EventDB.store_id == store_id)\
        .filter(EventDB.event_type.in_(["ZONE_ENTER", "ZONE_DWELL"]))\
        .filter(EventDB.is_staff == False).scalar() or 0

    # 3. Billing queue stage
    billing_queue_count = db.query(func.count(func.distinct(EventDB.visitor_id)))\
        .filter(EventDB.store_id == store_id)\
        .filter(EventDB.event_type == "BILLING_QUEUE_JOIN")\
        .filter(EventDB.is_staff == False).scalar() or 0

    # 4. Purchase stage (POS data pre-loaded at startup via lifespan)
    purchase_count = db.query(func.count(func.distinct(PosTransactionDB.matched_visitor_id)))\
        .filter(PosTransactionDB.store_id == store_id)\
        .filter(PosTransactionDB.matched_visitor_id.isnot(None))\
        .scalar() or 0

    # Calculations
    entry_to_zone_count = max(0, entry_count - zone_visit_count)
    entry_to_zone_percent = round((entry_to_zone_count / entry_count * 100), 2) if entry_count > 0 else 0.0

    zone_to_billing_count = max(0, zone_visit_count - billing_queue_count)
    zone_to_billing_percent = round((zone_to_billing_count / zone_visit_count * 100), 2) if zone_visit_count > 0 else 0.0

    billing_to_purchase_count = max(0, billing_queue_count - purchase_count)
    billing_to_purchase_percent = round((billing_to_purchase_count / billing_queue_count * 100), 2) if billing_queue_count > 0 else 0.0

    stages = {
        "entry": entry_count,
        "zone_visit": zone_visit_count,
        "billing_queue": billing_queue_count,
        "purchase": purchase_count
    }

    dropoffs = {
        "entry_to_zone": DropoffDetails(count=entry_to_zone_count, percent=entry_to_zone_percent),
        "zone_to_billing": DropoffDetails(count=zone_to_billing_count, percent=zone_to_billing_percent),
        "billing_to_purchase": DropoffDetails(count=billing_to_purchase_count, percent=billing_to_purchase_percent)
    }

    return FunnelResponse(
        store_id=store_id,
        stages=stages,
        dropoffs=dropoffs
    )
