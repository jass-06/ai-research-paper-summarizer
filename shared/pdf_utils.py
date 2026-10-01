"""PDF text extraction + smart text selection for the AI prompt."""
from __future__ import annotations

import re

try:  # PyMuPDF >= 1.24 prefers `import pymupdf`; older installs only have `fitz`
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore


def extract_pdf(pdf_bytes: bytes) -> dict:
    """Return {"text", "page_count", "metadata_title"}.

    Empty text means the PDF has no text layer (scanned/image-only) — the caller
    reports that clearly instead of sending an empty prompt to the AI.
    Raises ValueError for files that are not valid PDFs.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # corrupted / renamed non-PDF files
        raise ValueError(f"File could not be opened as a PDF: {exc}") from exc
    try:
        pages = [page.get_text("text") for page in doc]
        meta_title = (doc.metadata or {}).get("title") or ""
        page_count = doc.page_count
    finally:
        doc.close()

    text = "\n".join(pages)
    text = re.sub(r"[ \t]+", " ", text)          # collapse runs of spaces
    text = re.sub(r"\n{3,}", "\n\n", text).strip()  # collapse blank lines
    return {"text": text, "page_count": page_count, "metadata_title": meta_title.strip()}


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Backwards-compatible helper kept from v1."""
    return extract_pdf(pdf_bytes)["text"]


_CONCLUSION_MARKERS = re.compile(
    r"\n\s*(?:\d+\.?\s*)?(conclusions?|discussion|summary and conclusions?|limitations|future work)\s*\n",
    re.IGNORECASE,
)
_REFERENCES_MARKER = re.compile(r"\n\s*(references|bibliography)\s*\n", re.IGNORECASE)


def select_for_prompt(text: str, max_chars: int = 14000) -> str:
    """Pick the most informative parts of a long paper.

    v1 sent only the first 12k characters, so for most papers the AI never saw
    the results or the conclusion. Here we keep the head (title, abstract,
    intro, method) AND the conclusion/discussion, and drop the reference list.
    """
    ref = _REFERENCES_MARKER.search(text)
    if ref and ref.start() > len(text) * 0.5:
        text = text[: ref.start()]

    if len(text) <= max_chars:
        return text

    head_budget = int(max_chars * 0.6)
    tail_budget = max_chars - head_budget
    head = text[:head_budget]

    concl = None
    for m in _CONCLUSION_MARKERS.finditer(text):
        if m.start() > head_budget:
            concl = m
    tail_start = concl.start() if concl else len(text) - tail_budget
    tail = text[tail_start: tail_start + tail_budget]
    return f"{head}\n\n[... middle of paper omitted for length ...]\n\n{tail}"


def chunk_text(text: str, chunk_chars: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks for question answering."""
    chunks, start = [], 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9\-]{2,}")
_STOP = set("""the and for with that this from are was were has have had not but its into
than then they them their which what when where who how why can could would should may
might also been being our your you about over such these those there here using used use
paper study results method methods approach based between more most other some any all
each one two three""".split())


def top_chunks(text: str, question: str, k: int = 4) -> list[str]:
    """Lightweight retrieval (no vector DB needed): score each chunk by how many
    question terms it contains, weighted by term rarity across the paper."""
    chunks = chunk_text(text)
    if not chunks:
        return []
    q_terms = {w.lower() for w in _WORD.findall(question)} - _STOP
    if not q_terms:
        return chunks[:k]
    doc_freq = {t: sum(1 for c in chunks if t in c.lower()) for t in q_terms}
    scored = []
    for i, c in enumerate(chunks):
        low = c.lower()
        score = sum(low.count(t) / (1 + doc_freq[t]) for t in q_terms if t in low)
        scored.append((score, -i, c))
    scored.sort(reverse=True)
    best = [c for s, _, c in scored[:k] if s > 0]
    return best or chunks[:k]
