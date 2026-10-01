"""Real, verifiable related papers from the arXiv API (free, no key needed).

v1 asked the AI to suggest "plausible" related papers — i.e. titles that may
not exist. Here we look up REAL papers on arXiv using the extracted keywords
and return them with links, authors and year. AI suggestions are kept but
clearly labelled as unverified research directions.
"""
from __future__ import annotations

import os
import urllib.parse
import xml.etree.ElementTree as ET

import requests

ARXIV_URL = "https://export.arxiv.org/api/query"
_NS = {"a": "http://www.w3.org/2005/Atom"}


def enabled() -> bool:
    return os.environ.get("ENABLE_ARXIV", "true").lower() == "true"


def _query(search: str, max_results: int) -> list[dict]:
    params = {"search_query": search, "start": 0, "max_results": max_results, "sortBy": "relevance"}
    url = f"{ARXIV_URL}?{urllib.parse.urlencode(params)}"
    resp = requests.get(url, timeout=12, headers={"User-Agent": "ai-research-paper-summarizer/2.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    out = []
    for entry in root.findall("a:entry", _NS):
        title = " ".join((entry.findtext("a:title", "", _NS) or "").split())
        link = entry.findtext("a:id", "", _NS) or ""
        published = entry.findtext("a:published", "", _NS) or ""
        authors = [a.findtext("a:name", "", _NS) for a in entry.findall("a:author", _NS)]
        if title:
            out.append({
                "title": title,
                "url": link.replace("http://", "https://"),
                "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "year": published[:4],
            })
    return out


def find_related(keywords: list[str], own_title: str = "", limit: int = 5) -> list[dict]:
    """Best-effort lookup. Returns [] on any network/API problem — never fails the job."""
    if not enabled() or not keywords:
        return []
    terms = [k.replace('"', "") for k in keywords if 2 < len(k) < 60][:4]
    if not terms:
        return []
    try:
        strict = " AND ".join(f'all:"{t}"' for t in terms[:2])
        results = _query(strict, limit + 2)
        if len(results) < 3:
            loose = " OR ".join(f'all:"{t}"' for t in terms)
            results += _query(loose, limit + 2)
    except Exception:
        return []

    seen, out = {own_title.lower().strip()}, []
    for r in results:
        key = r["title"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        r.update({"reason": f"arXiv match for: {', '.join(terms[:2])}", "source": "arxiv", "verified": True})
        out.append(r)
        if len(out) >= limit:
            break
    return out
