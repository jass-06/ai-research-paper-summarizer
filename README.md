# 📄 PaperAI — AI Research Paper Summarizer

![CI](https://github.com/jass-06/ai-research-paper-summarizer/actions/workflows/ci.yml/badge.svg)

Upload research papers (PDF) and get a structured AI summary, a one-line TL;DR,
keywords, topics, **real related papers from arXiv**, a **chat-style Q&A over the
paper**, and a **multi-paper comparison** that surfaces research gaps.

Built as a cloud-native full-stack app: **React + Vite** · **FastAPI** · **AWS S3 / RDS PostgreSQL / Lambda / EC2 / CloudFront** · **Groq (Llama 3.3 70B)**.
Runs fully locally with zero AWS setup.

## Features

| Area | What it does |
|---|---|
| Analysis | Structured summary (Objective, Methodology, Key Findings, Limitations, Future Work), TL;DR, difficulty level, keywords, topics |
| Long papers | Sends the beginning **and** the conclusion to the AI, strips the reference list |
| Related work | Verified papers from the arXiv API (with links, authors, year) + clearly-labelled AI suggestions |
| Ask the paper | Ask questions; answers are grounded in retrieved passages, which are shown |
| Compare | Pick 2–6 papers → overview, common themes, differences, research gaps, reading order |
| Workflow | Drag & drop multi-upload, live status, search, retry, notes, Markdown export, open original PDF |
| Cloud | S3 or local disk, RDS/Postgres or SQLite, Lambda or in-process — switched by `.env` only |
| Quality | 10 automated tests, GitHub Actions CI, offline **mock AI mode** |

## Quick start (macOS)

Requirements: Python 3.11+ (`brew install python@3.12`), Node 18+ (`brew install node`).

```bash
make setup            # venv + dependencies + creates .env
# open .env and paste your free Groq key into GROQ_API_KEY (https://console.groq.com/keys)

make backend          # terminal 1 → API on http://localhost:8000
make frontend         # terminal 2 → app on http://localhost:5173
```
Upload `samples/sample_paper.pdf` to try it.

**No key yet?** `make demo` runs the whole app with placeholder AI output at http://localhost:8000.

<details><summary>Without make</summary>

```bash
cp .env.example .env
python3 -m venv backend/.venv && source backend/.venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend && uvicorn app.main:app --reload --port 8000
# new terminal
cd frontend && npm install && npm run dev
```
</details>

### Docker (adds a real PostgreSQL, like RDS)
```bash
cp .env.example .env    # add GROQ_API_KEY
docker compose up --build   # → http://localhost:8000
```

## Project structure
```
shared/      PDF extraction, AI calls, arXiv lookup, storage, processing pipeline (used by backend AND Lambda)
backend/     FastAPI app + tests (runs on EC2 in production)
lambda/      AWS Lambda handler + build script
frontend/    React (Vite) single-page app
infra/       AWS deployment guide, IAM policies, RDS schema, Lambda deploy script
samples/     sample PDF for testing
```

## API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | DB, storage, processing mode, AI and arXiv status |
| GET | `/api/stats` | Counts, pages read, top topics |
| POST | `/api/papers/upload` | Upload a PDF (validated, size-limited) and start processing |
| GET | `/api/papers?q=` | List / search papers |
| GET | `/api/papers/{id}` | One paper with all results |
| PATCH | `/api/papers/{id}/notes` | Save notes |
| POST | `/api/papers/{id}/reprocess` | Retry / re-run AI |
| POST | `/api/papers/{id}/ask` | Question answering over the paper |
| POST | `/api/papers/compare` | Compare 2–6 papers |
| GET | `/api/papers/{id}/export.md` | Markdown export |
| GET | `/api/papers/{id}/pdf` | Original PDF (presigned S3 URL in cloud mode) |
| DELETE | `/api/papers/{id}` | Delete paper **and** its stored files |

Interactive docs: http://localhost:8000/docs

## Deploying to AWS
See [`infra/deploy-aws.md`](infra/deploy-aws.md) — Tier 1 (EC2 + S3 + RDS + CloudFront) and Tier 2 (+ Lambda).

## Tests
```bash
make test     # runs offline with mock AI, temp SQLite and temp storage
```

## Known limitations
- No user accounts yet — anyone with the URL sees all papers (next step: Amazon Cognito).
- No OCR for scanned PDFs (detected and reported; next step: Amazon Textract).
- Q&A uses keyword retrieval, not embeddings.
- Lambda mode needs a NAT Gateway for internet access (see the deploy guide).

## Author
Built by [Jaspreet](https://github.com/jass-06)

## License
MIT
