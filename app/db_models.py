from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class EventDB(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)
    store_id = Column(String, index=True)
    camera_id = Column(String)
    visitor_id = Column(String, index=True)
    event_type = Column(String)
    timestamp = Column(DateTime, index=True)
    zone_id = Column(String, nullable=True)
    dwell_ms = Column(Integer)
    is_staff = Column(Boolean)
    confidence = Column(Float)
    metadata_json = Column(String)
    created_at = Column(DateTime)

class PosTransactionDB(Base):
    __tablename__ = "pos_transactions"
    
    transaction_id = Column(String, primary_key=True)
    store_id = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    basket_value_inr = Column(Float)
    matched_visitor_id = Column(String, nullable=True)
