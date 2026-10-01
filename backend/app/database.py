from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added in v2. If you already ran v1 against a database, they are added
# automatically on startup (a tiny, safe "migration" — create_all never alters tables).
_V2_COLUMNS = {
    "title": "VARCHAR(500)",
    "tldr": "TEXT",
    "difficulty": "VARCHAR(20)",
    "page_count": "INTEGER",
    "word_count": "INTEGER",
    "text_path": "VARCHAR(512)",
    "model_used": "VARCHAR(100)",
    "processing_seconds": "FLOAT",
    "file_size_bytes": "INTEGER",
}


def init_db():
    from . import models  # noqa: F401  (registers the models)

    Base.metadata.create_all(bind=engine)
    existing = {c["name"] for c in inspect(engine).get_columns("papers")}
    with engine.begin() as conn:
        for name, ddl in _V2_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE papers ADD COLUMN {name} {ddl}"))
