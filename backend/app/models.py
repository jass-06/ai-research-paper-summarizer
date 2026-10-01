from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator

from .database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GUID(TypeDecorator):
    """Postgres UUID on RDS, CHAR(36) on SQLite — same model everywhere."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        return None if value is None else str(value)

    def process_result_value(self, value, dialect):
        return None if value is None else str(value)


class Paper(Base):
    __tablename__ = "papers"

    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String(255), nullable=False)
    s3_pdf_path = Column(String(512), nullable=False)
    s3_output_path = Column(String(512), nullable=True)
    text_path = Column(String(512), nullable=True)

    status = Column(String(20), nullable=False, default="uploaded", index=True)
    # uploaded -> processing -> done | error

    title = Column(String(500), nullable=True)
    tldr = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)
    topics = Column(JSON, nullable=True)
    related_papers = Column(JSON, nullable=True)
    difficulty = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True, default="")
    error_message = Column(Text, nullable=True)

    page_count = Column(Integer, nullable=True)
    word_count = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    model_used = Column(String(100), nullable=True)
    processing_seconds = Column(Float, nullable=True)

    created_at = Column(DateTime, default=utcnow, index=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
