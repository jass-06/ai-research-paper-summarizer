"""Central configuration. Imported FIRST so .env is loaded before anything reads env vars
(v1 imported the shared package before loading .env, so some settings were ignored)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

# Load .env from the repo root (and backend/.env if someone puts it there)
load_dotenv(REPO_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env")

# Local data lives in backend/data regardless of which folder you start uvicorn from
DATA_DIR = Path(os.environ.get("DATA_DIR", BACKEND_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("LOCAL_STORAGE_DIR", str(DATA_DIR / "storage"))

DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{DATA_DIR / 'local.db'}"

# Comma-separated list of allowed browser origins
FRONTEND_ORIGINS = [o.strip() for o in os.environ.get(
    "FRONTEND_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# true  -> process in a background task inside FastAPI (no AWS needed)
# false -> hand off to AWS Lambda asynchronously
LOCAL_PROCESSING = os.environ.get("LOCAL_PROCESSING", "true").lower() == "true"

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_LAMBDA_FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "")

MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB", "25"))
STALE_PROCESSING_MINUTES = int(os.environ.get("STALE_PROCESSING_MINUTES", "15"))

APP_VERSION = "2.0.0"
