import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.db_models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./store_intelligence.db")

is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    pool_pre_ping=True,           # verify connection is alive before using it
)

# Enable WAL mode for SQLite so concurrent reads don't block each other
if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_wal_mode(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")  # safe + faster than FULL

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
