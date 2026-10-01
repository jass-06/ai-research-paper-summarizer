"""FastAPI backend for the AI Research Paper Summarizer (v2).

Runs locally (SQLite + local disk + background processing) or on AWS
(EC2 + RDS PostgreSQL + S3 + Lambda) — switched purely by environment variables.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from . import config  # MUST be first: loads .env before anything reads env vars

sys.path.insert(0, str(config.REPO_ROOT))  # make the repo-root `shared/` package importable
from shared import ai, pipeline, related, storage  # noqa: E402

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import PlainTextResponse, RedirectResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from . import crud, schemas  # noqa: E402
from .database import SessionLocal, get_db, init_db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("paperai")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as db:
        n = crud.fail_stale_jobs(db, config.STALE_PROCESSING_MINUTES)
        if n:
            log.warning("Marked %s interrupted job(s) as error", n)
    log.info("Started v%s | db=%s | storage=%s | processing=%s | ai=%s",
             config.APP_VERSION, config.DATABASE_URL.split(":")[0], storage.backend(),
             "inline" if config.LOCAL_PROCESSING else "lambda", ai.provider())
    yield


app = FastAPI(title="AI Research Paper Summarizer API", version=config.APP_VERSION, lifespan=lifespan)

# v1 used allow_origins=["*"] together with allow_credentials=True, which browsers
# reject and which is unsafe. We allow only the configured frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------
def process_in_background(paper_id: str) -> None:
    """Runs the shared pipeline with its OWN db session (the request's session is
    closed by the time a background task runs)."""
    with SessionLocal() as db:
        paper = crud.get_paper(db, paper_id)
        if not paper:
            return
        crud.set_status(db, paper_id, "processing")
        try:
            fields = pipeline.run(paper.s3_pdf_path)
            crud.save_result(db, paper_id, fields)
            log.info("Processed %s in %ss", paper_id, fields.get("processing_seconds"))
        except pipeline.NoTextError as exc:
            crud.set_status(db, paper_id, "error", str(exc))
        except Exception as exc:  # surfaced to the UI, logged for us
            log.exception("Processing failed for %s", paper_id)
            crud.set_status(db, paper_id, "error", str(exc)[:2000])


def _invoke_lambda(paper_id: str, s3_key: str) -> None:
    import boto3

    boto3.client("lambda", region_name=config.AWS_REGION).invoke(
        FunctionName=config.AWS_LAMBDA_FUNCTION_NAME,
        InvocationType="Event",  # async, fire-and-forget
        Payload=json.dumps({"paper_id": paper_id, "s3_key": s3_key}).encode(),
    )


def _dispatch(db: Session, paper_id: str, s3_key: str, background: BackgroundTasks) -> None:
    if config.LOCAL_PROCESSING:
        background.add_task(process_in_background, paper_id)
        return
    try:
        _invoke_lambda(paper_id, s3_key)
        crud.set_status(db, paper_id, "processing")
    except Exception as exc:
        log.exception("Lambda invoke failed")
        crud.set_status(db, paper_id, "error", f"Could not start AWS Lambda: {exc}"[:2000])


# ---------------------------------------------------------------------------
# Health & stats
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=schemas.HealthOut)
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return schemas.HealthOut(
        status="ok" if db_ok else "degraded",
        version=config.APP_VERSION,
        database=db_ok,
        database_engine=db.bind.dialect.name,
        storage_backend="s3" if storage.is_cloud_storage() else "local-disk",
        processing_mode="inline (background task)" if config.LOCAL_PROCESSING else "AWS Lambda (async)",
        ai_provider=ai.provider(),
        ai_model=ai.model_name(),
        ai_configured=ai.is_configured(),
        arxiv_enabled=related.enabled(),
    )


@app.get("/api/stats", response_model=schemas.StatsOut)
def get_stats(db: Session = Depends(get_db)):
    return crud.stats(db)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------
@app.post("/api/papers/upload", response_model=schemas.PaperOut, status_code=201)
async def upload_paper(background: BackgroundTasks, file: UploadFile = File(...),
                       db: Session = Depends(get_db)):
    filename = storage.safe_filename(file.filename or "paper.pdf")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty.")
    if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_MB:g} MB.")
    if not content[:1024].lstrip().startswith(b"%PDF"):
        raise HTTPException(400, "This file is not a valid PDF (missing PDF header).")

    file_id = str(uuid.uuid4())
    date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    s3_key = f"uploads/{date_prefix}/{file_id}_{filename}"
    storage.put_object(s3_key, content, "application/pdf")

    paper = crud.create_paper(db, filename=filename, s3_pdf_path=s3_key, size=len(content))
    _dispatch(db, paper.id, s3_key, background)
    db.refresh(paper)
    return paper


# ---------------------------------------------------------------------------
# Read / list / notes / reprocess / delete
# ---------------------------------------------------------------------------
@app.get("/api/papers", response_model=List[schemas.PaperOut])
def list_papers(q: Optional[str] = Query(None, max_length=200), status: Optional[str] = None,
                db: Session = Depends(get_db)):
    return crud.list_papers(db, q=q, status=status)


def _get_or_404(db: Session, paper_id: str):
    paper = crud.get_paper(db, paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found")
    return paper


@app.get("/api/papers/{paper_id}", response_model=schemas.PaperOut)
def get_paper(paper_id: str, db: Session = Depends(get_db)):
    return _get_or_404(db, paper_id)


@app.patch("/api/papers/{paper_id}/notes", response_model=schemas.PaperOut)
def update_notes(paper_id: str, body: schemas.NotesUpdate, db: Session = Depends(get_db)):
    _get_or_404(db, paper_id)
    return crud.update_notes(db, paper_id, body.notes)


@app.post("/api/papers/{paper_id}/reprocess", response_model=schemas.PaperOut)
def reprocess_paper(paper_id: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    paper = _get_or_404(db, paper_id)
    if paper.status == "processing":
        raise HTTPException(409, "This paper is already being processed.")
    crud.set_status(db, paper.id, "uploaded")
    _dispatch(db, paper.id, paper.s3_pdf_path, background)
    db.refresh(paper)
    return paper


@app.delete("/api/papers/{paper_id}")
def delete_paper(paper_id: str, db: Session = Depends(get_db)):
    paper = _get_or_404(db, paper_id)
    for key in (paper.s3_pdf_path, paper.s3_output_path, paper.text_path):
        storage.delete_object(key)  # v1 left orphaned files behind in S3 / disk
    crud.delete_paper(db, paper)
    return {"deleted": True}


@app.get("/api/papers/{paper_id}/pdf")
def download_pdf(paper_id: str, db: Session = Depends(get_db)):
    paper = _get_or_404(db, paper_id)
    url = storage.presigned_url(paper.s3_pdf_path)
    if url:
        return RedirectResponse(url)
    return Response(storage.get_object(paper.s3_pdf_path), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{paper.original_filename}"'})


# ---------------------------------------------------------------------------
# New in v2: Ask, Compare, Export
# ---------------------------------------------------------------------------
@app.post("/api/papers/{paper_id}/ask", response_model=schemas.AskOut)
def ask_paper(paper_id: str, body: schemas.AskIn, db: Session = Depends(get_db)):
    paper = _get_or_404(db, paper_id)
    if paper.status != "done" or not paper.text_path:
        raise HTTPException(409, "The paper must finish processing before you can ask questions.")
    full_text = storage.get_object(paper.text_path).decode("utf-8", errors="ignore")
    try:
        return ai.answer_question(full_text, body.question)
    except Exception as exc:
        raise HTTPException(502, f"AI request failed: {exc}") from exc


@app.post("/api/papers/compare", response_model=schemas.CompareOut)
def compare(body: schemas.CompareIn, db: Session = Depends(get_db)):
    papers = [crud.get_paper(db, pid) for pid in dict.fromkeys(body.paper_ids)]
    papers = [p for p in papers if p and p.status == "done"]
    if len(papers) < 2:
        raise HTTPException(400, "Select at least two processed papers to compare.")
    payload = [{"title": p.title or p.original_filename, "tldr": p.tldr, "summary": p.summary,
                "keywords": p.keywords, "topics": p.topics} for p in papers]
    try:
        result = ai.compare_papers(payload)
    except Exception as exc:
        raise HTTPException(502, f"AI request failed: {exc}") from exc
    return {"papers": [p["title"] for p in payload], **result}


@app.get("/api/papers/{paper_id}/export.md", response_class=PlainTextResponse)
def export_markdown(paper_id: str, db: Session = Depends(get_db)):
    p = _get_or_404(db, paper_id)
    if p.status != "done":
        raise HTTPException(409, "Paper is not processed yet.")
    lines = [f"# {p.title or p.original_filename}", ""]
    if p.tldr:
        lines += [f"> **TL;DR:** {p.tldr}", ""]
    lines += [f"*File:* {p.original_filename} · *Pages:* {p.page_count or '-'} · "
              f"*Difficulty:* {p.difficulty or '-'}", "", "## Summary", ""]
    for block in (p.summary or "").split("\n\n"):
        if ":" in block[:40]:
            head, body = block.split(":", 1)
            lines += [f"### {head.strip()}", body.strip(), ""]
        else:
            lines += [block, ""]
    lines += ["## Keywords", ", ".join(p.keywords or []), "", "## Topics", ", ".join(p.topics or []), "",
              "## Related papers"]
    for r in p.related_papers or []:
        tag = "verified on arXiv" if r.get("verified") else "AI-suggested direction"
        link = f"[{r.get('title')}]({r['url']})" if r.get("url") else r.get("title")
        lines.append(f"- {link} — {r.get('reason', '')} *({tag})*")
    if p.notes:
        lines += ["", "## My notes", p.notes]
    safe = Path(p.original_filename).stem.replace('"', "")
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="{safe}-summary.md"'})


# ---------------------------------------------------------------------------
# Optional: serve the built React app from the same server (single-container deploy,
# avoids HTTPS -> HTTP "mixed content" problems). Only active if frontend/dist exists.
# ---------------------------------------------------------------------------
_dist = Path(os.environ.get("FRONTEND_DIST", config.REPO_ROOT / "frontend" / "dist"))
if _dist.is_dir() and os.environ.get("SERVE_FRONTEND", "true").lower() == "true":
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
