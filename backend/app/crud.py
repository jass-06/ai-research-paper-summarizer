from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models


def create_paper(db: Session, filename: str, s3_pdf_path: str, size: int) -> models.Paper:
    paper = models.Paper(original_filename=filename, s3_pdf_path=s3_pdf_path,
                         status="uploaded", file_size_bytes=size)
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


def get_paper(db: Session, paper_id: str) -> Optional[models.Paper]:
    return db.query(models.Paper).filter(models.Paper.id == paper_id).first()


def list_papers(db: Session, q: Optional[str] = None, status: Optional[str] = None):
    query = db.query(models.Paper)
    if status:
        query = query.filter(models.Paper.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(models.Paper.original_filename.ilike(like),
                                 models.Paper.title.ilike(like),
                                 models.Paper.summary.ilike(like)))
    return query.order_by(models.Paper.created_at.desc()).all()


def set_status(db: Session, paper_id: str, status: str, error_message: Optional[str] = None):
    paper = get_paper(db, paper_id)
    if not paper:
        return None
    paper.status = status
    paper.error_message = error_message
    db.commit()
    db.refresh(paper)
    return paper


def save_result(db: Session, paper_id: str, fields: dict):
    paper = get_paper(db, paper_id)
    if not paper:
        return None
    for key, value in fields.items():
        if hasattr(paper, key):
            setattr(paper, key, value)
    paper.status = "done"
    paper.error_message = None
    db.commit()
    db.refresh(paper)
    return paper


def update_notes(db: Session, paper_id: str, notes: str):
    paper = get_paper(db, paper_id)
    if not paper:
        return None
    paper.notes = notes
    db.commit()
    db.refresh(paper)
    return paper


def delete_paper(db: Session, paper: models.Paper) -> None:
    db.delete(paper)
    db.commit()


def stats(db: Session) -> dict:
    papers = db.query(models.Paper).all()
    topics = Counter(t for p in papers if p.topics for t in p.topics)
    return {
        "total": len(papers),
        "done": sum(p.status == "done" for p in papers),
        "processing": sum(p.status in ("uploaded", "processing") for p in papers),
        "failed": sum(p.status == "error" for p in papers),
        "total_pages": sum(p.page_count or 0 for p in papers),
        "top_topics": [{"topic": t, "count": c} for t, c in topics.most_common(8)],
    }


def fail_stale_jobs(db: Session, minutes: int) -> int:
    """Jobs left in 'processing' (e.g. the server restarted mid-job) are marked as
    failed so the user can press Retry instead of waiting forever."""
    cutoff = models.utcnow() - timedelta(minutes=minutes)
    stale = db.query(models.Paper).filter(models.Paper.status.in_(["uploaded", "processing"]),
                                          models.Paper.updated_at < cutoff).all()
    for p in stale:
        p.status = "error"
        p.error_message = "Processing was interrupted (server restart or timeout). Click Retry."
    db.commit()
    return len(stale)
