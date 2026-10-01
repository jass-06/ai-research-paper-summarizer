def _upload(client, data, name="paper.pdf"):
    return client.post("/api/papers/upload", files={"file": (name, data, "application/pdf")})


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["ai_provider"] == "mock" and body["ai_configured"]


def test_full_lifecycle(client, sample_pdf):
    r = _upload(client, sample_pdf)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    # TestClient runs background tasks before returning, so processing is complete
    paper = client.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "done", paper.get("error_message")
    assert paper["summary"] and paper["keywords"] and paper["page_count"] == 1
    assert paper["word_count"] > 100

    assert client.patch(f"/api/papers/{pid}/notes", json={"notes": "great"}).json()["notes"] == "great"

    ans = client.post(f"/api/papers/{pid}/ask", json={"question": "How much did food waste fall?"})
    assert ans.status_code == 200 and ans.json()["excerpts"]

    md = client.get(f"/api/papers/{pid}/export.md")
    assert md.status_code == 200 and "## Summary" in md.text

    assert client.get(f"/api/papers/{pid}/pdf").content.startswith(b"%PDF")
    assert client.get("/api/papers", params={"q": "paper"}).json()

    assert client.post(f"/api/papers/{pid}/reprocess").json()["status"] in ("uploaded", "done")
    assert client.delete(f"/api/papers/{pid}").json() == {"deleted": True}
    assert client.get(f"/api/papers/{pid}").status_code == 404


def test_compare(client, sample_pdf):
    ids = [_upload(client, sample_pdf, f"p{i}.pdf").json()["id"] for i in range(2)]
    r = client.post("/api/papers/compare", json={"paper_ids": ids})
    assert r.status_code == 200 and len(r.json()["papers"]) == 2
    assert client.get("/api/stats").json()["done"] >= 2


def test_rejects_non_pdf(client):
    assert _upload(client, b"hello", "notes.txt").status_code == 400
    assert _upload(client, b"not really a pdf", "fake.pdf").status_code == 400
    assert _upload(client, b"", "empty.pdf").status_code == 400


def test_path_traversal_is_neutralised(client, sample_pdf):
    r = _upload(client, sample_pdf, "../../../evil.pdf")
    assert r.status_code == 201
    assert r.json()["original_filename"] == "evil.pdf"


def test_scanned_pdf_reports_clear_error(client):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open()
    doc.new_page()  # blank page = no text layer, like a scan
    pid = _upload(client, doc.tobytes(), "scan.pdf").json()["id"]
    paper = client.get(f"/api/papers/{pid}").json()
    assert paper["status"] == "error" and "scanned" in paper["error_message"]
