"""AI layer — one place for every model call.

Providers (set AI_PROVIDER):
  * groq  (default) — Groq's OpenAI-compatible API, free tier, Llama 3.3 70B.
  * mock            — no network, deterministic output. Lets you run the whole
                      app, the tests and CI without any API key.

Improvements over v1:
  * JSON mode (response_format=json_object) -> far fewer malformed replies.
  * Retry with exponential back-off on 429 rate limits and 5xx errors
    (v1 failed the whole job on a single rate-limit hit).
  * Settings are read at call time, so values from .env are always honoured.
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter

import requests

from . import pdf_utils

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def provider() -> str:
    return os.environ.get("AI_PROVIDER", "groq").strip().lower()


def is_configured() -> bool:
    return provider() == "mock" or bool(os.environ.get("GROQ_API_KEY"))


def model_name() -> str:
    if provider() == "mock":
        return "mock"
    return os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


# ---------------------------------------------------------------------------
# Low-level call with retries
# ---------------------------------------------------------------------------
def _chat(messages: list[dict], json_mode: bool = False, max_tokens: int = 2000) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file, "
            "or set AI_PROVIDER=mock to try the app without a key."
        )
    payload = {
        "model": model_name(),
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    max_attempts = int(os.environ.get("AI_MAX_RETRIES", "4"))
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=90)
        except requests.RequestException as exc:
            last_error = f"network error: {exc}"
        else:
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            last_error = f"Groq API error {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in (429, 500, 502, 503, 504):
                break  # 400/401 etc. will not fix themselves — fail fast
            retry_after = resp.headers.get("retry-after")
            if retry_after and retry_after.replace(".", "", 1).isdigit():
                time.sleep(min(float(retry_after), 30))
                continue
        if attempt < max_attempts:
            time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(last_error or "AI call failed")


def _extract_json(raw: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    return json.loads(match.group(0) if match else cleaned)


def _str_list(value, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        s = str(v).strip()
        if s and s.lower() not in {x.lower() for x in out}:
            out.append(s)
    return out[:limit]


# ---------------------------------------------------------------------------
# 1) Paper analysis
# ---------------------------------------------------------------------------
ANALYSIS_PROMPT = """You are an expert academic research assistant. Analyse the research
paper text below. Respond with ONE JSON object only, with exactly these keys:

"title":          the paper's real title (string; "" if you cannot tell)
"tldr":           one plain-English sentence a non-expert would understand
"summary":        an object with keys "objective", "methodology", "key_findings",
                  "limitations", "future_work" — each 2-4 sentences, grounded ONLY in the text
"keywords":       10-15 important technical terms (strings)
"topics":         3-6 short topic/theme labels (strings)
"related_directions": 3-5 objects {{"title": ..., "reason": ...}} describing research
                  directions or well-known related works. Do not invent citations.
"difficulty":     one of "introductory", "intermediate", "advanced"

If a section is not covered by the text, say "Not stated in the paper." Never guess numbers.

Paper text:
{text}
"""

SUMMARY_SECTIONS = [
    ("objective", "Objective"),
    ("methodology", "Methodology"),
    ("key_findings", "Key Findings"),
    ("limitations", "Limitations"),
    ("future_work", "Future Work"),
]


def _summary_to_text(summary) -> str:
    if isinstance(summary, str):
        return summary.strip()
    if isinstance(summary, dict):
        parts = []
        for key, label in SUMMARY_SECTIONS:
            val = str(summary.get(key, "")).strip() or "Not stated in the paper."
            parts.append(f"{label}: {val}")
        return "\n\n".join(parts)
    return ""


def analyze_paper(text: str) -> dict:
    """Returns {title, tldr, summary, keywords, topics, related_papers, difficulty}.
    Never raises on a malformed model reply — degrades to the raw text instead."""
    if provider() == "mock":
        return _mock_analysis(text)

    max_chars = int(os.environ.get("AI_MAX_INPUT_CHARS", "14000"))
    prompt = ANALYSIS_PROMPT.format(text=pdf_utils.select_for_prompt(text, max_chars))
    raw = _chat([{"role": "user", "content": prompt}], json_mode=True)
    try:
        data = _extract_json(raw)
        related = []
        for r in data.get("related_directions", data.get("related_papers", []))[:5]:
            if isinstance(r, dict) and r.get("title"):
                related.append({
                    "title": str(r["title"]).strip(),
                    "reason": str(r.get("reason", "")).strip(),
                    "source": "ai",
                    "verified": False,
                })
        difficulty = str(data.get("difficulty", "")).lower()
        return {
            "title": str(data.get("title", "")).strip(),
            "tldr": str(data.get("tldr", "")).strip(),
            "summary": _summary_to_text(data.get("summary", "")),
            "keywords": _str_list(data.get("keywords"), 15),
            "topics": _str_list(data.get("topics"), 6),
            "related_papers": related,
            "difficulty": difficulty if difficulty in {"introductory", "intermediate", "advanced"} else "",
        }
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return {"title": "", "tldr": "", "summary": raw.strip(), "keywords": [],
                "topics": [], "related_papers": [], "difficulty": ""}


# ---------------------------------------------------------------------------
# 2) Ask a question about one paper (retrieval over the stored full text)
# ---------------------------------------------------------------------------
QA_PROMPT = """Answer the question using ONLY the excerpts from the research paper below.
If the excerpts do not contain the answer, say so honestly. Be concise (max ~150 words)
and mention which excerpt number(s) you used, e.g. [2].

{excerpts}

Question: {question}
"""


def answer_question(full_text: str, question: str) -> dict:
    excerpts = pdf_utils.top_chunks(full_text, question, k=4)
    if provider() == "mock":
        first = excerpts[0][:400] if excerpts else ""
        return {"answer": f"[mock mode] Most relevant passage [1]: {first}", "excerpts": excerpts}
    numbered = "\n\n".join(f"[{i + 1}] {e}" for i, e in enumerate(excerpts))
    answer = _chat([{"role": "user", "content": QA_PROMPT.format(excerpts=numbered, question=question)}],
                   max_tokens=500)
    return {"answer": answer.strip(), "excerpts": excerpts}


# ---------------------------------------------------------------------------
# 3) Compare several papers (mini literature review)
# ---------------------------------------------------------------------------
COMPARE_PROMPT = """You are writing a short literature-review style comparison of the
research papers below (each given as its AI summary). Respond with ONE JSON object:

"overview":      3-5 sentences on what these papers collectively cover
"common_themes": 3-6 strings
"differences":   3-6 strings, each naming the papers involved
"research_gaps": 2-5 strings — open questions none of the papers fully answer
"reading_order": list of paper titles in the order a newcomer should read them

Papers:
{papers}
"""


def compare_papers(papers: list[dict]) -> dict:
    if provider() == "mock":
        all_kw = Counter(k for p in papers for k in (p.get("keywords") or []))
        return {
            "overview": f"[mock mode] Comparison of {len(papers)} papers.",
            "common_themes": [k for k, _ in all_kw.most_common(4)],
            "differences": [f"{p['title']} focuses on {', '.join((p.get('topics') or ['-'])[:2])}" for p in papers],
            "research_gaps": ["Run with a real AI key to get genuine research gaps."],
            "reading_order": [p["title"] for p in papers],
        }
    blocks = "\n\n".join(
        f"### {p['title']}\nTL;DR: {p.get('tldr', '')}\n{(p.get('summary') or '')[:2500]}" for p in papers
    )
    raw = _chat([{"role": "user", "content": COMPARE_PROMPT.format(papers=blocks)}], json_mode=True)
    try:
        data = _extract_json(raw)
        return {
            "overview": str(data.get("overview", "")).strip(),
            "common_themes": _str_list(data.get("common_themes"), 8),
            "differences": _str_list(data.get("differences"), 8),
            "research_gaps": _str_list(data.get("research_gaps"), 8),
            "reading_order": _str_list(data.get("reading_order"), 20),
        }
    except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
        return {"overview": raw.strip(), "common_themes": [], "differences": [],
                "research_gaps": [], "reading_order": []}


# ---------------------------------------------------------------------------
# Mock provider (offline, deterministic)
# ---------------------------------------------------------------------------
def _mock_analysis(text: str) -> dict:
    words = re.findall(r"[A-Za-z][A-Za-z\-]{4,}", text)
    common = [w for w, _ in Counter(w.lower() for w in words).most_common(60)
              if w not in pdf_utils._STOP][:12]
    first_line = next((ln.strip() for ln in text.splitlines() if len(ln.strip()) > 10), "Untitled paper")
    return {
        "title": first_line[:150],
        "tldr": "[mock mode] This is placeholder output — set AI_PROVIDER=groq and a GROQ_API_KEY for real summaries.",
        "summary": "\n\n".join(f"{label}: [mock] {text[i * 200:(i + 1) * 200].strip()}..."
                               for i, (_, label) in enumerate(SUMMARY_SECTIONS)),
        "keywords": common[:12],
        "topics": [c.title() for c in common[:4]],
        "related_papers": [{"title": f"Further reading on {c}", "reason": "Mock suggestion.",
                            "source": "ai", "verified": False} for c in common[:3]],
        "difficulty": "intermediate",
    }
