"""Atlas Accounts Service — database setup (SQLAlchemy 2.0)."""
from __future__ import annotations

import sys
import os

# Allow running with local .lib install
_lib = os.path.join(os.path.dirname(__file__), ".lib")
if _lib not in sys.path:
    sys.path.insert(0, _lib)

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

# SQLite: enable WAL mode and foreign key enforcement
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (idempotent)."""
    from . import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
