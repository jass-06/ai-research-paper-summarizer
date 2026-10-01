"""Test setup: isolated temp SQLite DB + temp storage + offline mock AI.
No network, no API key, no AWS needed."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="paperai-test-")
os.environ.update({
    "DATA_DIR": _tmp,
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "LOCAL_STORAGE_DIR": f"{_tmp}/storage",
    "STORAGE_BACKEND": "local",
    "AI_PROVIDER": "mock",
    "ENABLE_ARXIV": "false",
    "LOCAL_PROCESSING": "true",
    "SERVE_FRONTEND": "false",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "sample_paper.pdf"


@pytest.fixture(scope="session")
def client():
    if not SAMPLE.exists():
        import subprocess
        subprocess.run([sys.executable, str(SAMPLE.parents[1] / "scripts" / "make_sample_pdf.py")], check=True)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def sample_pdf():
    return SAMPLE.read_bytes()
