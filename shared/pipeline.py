"""The single processing pipeline run by BOTH the backend (inline mode) and Lambda.

PDF bytes -> text -> AI analysis -> real related papers -> artefacts in storage.
"""
from __future__ import annotations

import json
import time

from . import ai, pdf_utils, related, storage


class NoTextError(Exception):
    """Raised for scanned / image-only PDFs that have no text layer."""


def derived_keys(pdf_key: str) -> tuple[str, str]:
    """uploads/2026-10-01/<id>_x.pdf -> processed/.../<id>_x.json and text/.../<id>_x.txt"""
    stem = pdf_key[:-4] if pdf_key.lower().endswith(".pdf") else pdf_key
    rest = stem.split("/", 1)[1] if "/" in stem else stem
    return f"processed/{rest}.json", f"text/{rest}.txt"


def run(pdf_key: str) -> dict:
    """Process one stored PDF. Returns the fields to save on the `papers` row."""
    started = time.time()
    pdf = pdf_utils.extract_pdf(storage.get_object(pdf_key))
    text = pdf["text"]
    if len(text) < 200:
        raise NoTextError(
            "No extractable text found — this looks like a scanned/image-only PDF. "
            "OCR is not enabled (see 'Future enhancements' in the docs)."
        )

    analysis = ai.analyze_paper(text)
    title = analysis.get("title") or pdf["metadata_title"]

    verified = related.find_related(analysis.get("keywords", []), own_title=title)
    analysis["related_papers"] = verified + analysis.get("related_papers", [])

    output_key, text_key = derived_keys(pdf_key)
    storage.put_object(text_key, text.encode("utf-8"), "text/plain; charset=utf-8")
    storage.put_object(output_key, json.dumps(analysis, indent=2).encode(), "application/json")

    return {
        "title": title[:500] if title else None,
        "tldr": analysis.get("tldr") or None,
        "summary": analysis.get("summary"),
        "keywords": analysis.get("keywords", []),
        "topics": analysis.get("topics", []),
        "related_papers": analysis["related_papers"],
        "difficulty": analysis.get("difficulty") or None,
        "page_count": pdf["page_count"],
        "word_count": len(text.split()),
        "s3_output_path": output_key,
        "text_path": text_key,
        "model_used": ai.model_name(),
        "processing_seconds": round(time.time() - started, 1),
    }
