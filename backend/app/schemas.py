from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PaperOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    status: str
    title: Optional[str] = None
    tldr: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[list] = None
    topics: Optional[list] = None
    related_papers: Optional[list] = None
    difficulty: Optional[str] = None
    notes: Optional[str] = None
    error_message: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    file_size_bytes: Optional[int] = None
    model_used: Optional[str] = None
    processing_seconds: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class NotesUpdate(BaseModel):
    notes: str = Field(max_length=20000)


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class AskOut(BaseModel):
    answer: str
    excerpts: List[str]


class CompareIn(BaseModel):
    paper_ids: List[str] = Field(min_length=2, max_length=6)


class CompareOut(BaseModel):
    papers: List[str]
    overview: str
    common_themes: List[str]
    differences: List[str]
    research_gaps: List[str]
    reading_order: List[str]


class StatsOut(BaseModel):
    total: int
    done: int
    processing: int
    failed: int
    total_pages: int
    top_topics: List[dict]


class HealthOut(BaseModel):
    status: str
    version: str
    database: bool
    database_engine: str
    storage_backend: str
    processing_mode: str
    ai_provider: str
    ai_model: str
    ai_configured: bool
    arxiv_enabled: bool
