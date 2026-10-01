# Architecture (v2)

```
                    HTTPS (one domain)
 Browser ───────────► CloudFront ───────────────┐
                                                ▼
                          ┌──────────────────────────────────────┐
                          │ EC2 · Docker container                │
                          │  FastAPI  /api/*   +  React build  /  │
                          └───────┬──────────────────┬───────────┘
                    PDFs, JSON,   │                  │  metadata, status,
                    full text     ▼                  ▼  results, notes
                          ┌──────────────┐   ┌──────────────────┐
                          │ S3 (private) │   │ RDS PostgreSQL    │
                          │ uploads/     │   │ papers table      │
                          │ processed/   │   └──────────────────┘
                          │ text/        │            ▲
                          └──────┬───────┘            │ UPDATE status/results
                                 │                    │
        LOCAL_PROCESSING=true    │   LOCAL_PROCESSING=false (async invoke)
        → FastAPI background     ▼                    │
          task runs the       ┌────────────────────────┴─┐
          same pipeline       │ AWS Lambda (in RDS VPC)   │──► Groq API (via NAT)
                              │ shared.pipeline.run()     │──► arXiv API (via NAT)
                              └───────────────────────────┘
```

## The pipeline (`shared/pipeline.py`) — identical in both modes
1. Read the PDF from storage; extract text + page count (PyMuPDF). Fewer than 200 characters → "scanned PDF" error.
2. Select text for the prompt: first 60% budget from the start, 40% from the conclusion/discussion; reference list removed.
3. One AI call in JSON mode → title, TL;DR, 5-section summary, keywords, topics, difficulty, research directions.
4. arXiv lookup with the top keywords → verified related papers (best effort; never fails the job).
5. Save `processed/*.json` and `text/*.txt` to storage; save fields to the `papers` row.

## Status lifecycle
`uploaded → processing → done | error`. On startup, jobs stuck in `uploaded/processing`
for more than 15 minutes are marked `error` so the user can retry.

## Ask the paper
The full text is split into 1,200-character overlapping chunks. Chunks are scored by
question-term overlap weighted by rarity (a lightweight TF-IDF), the top 4 are sent to the
model with an instruction to answer only from them, and they are shown to the user.
Upgrade path: embeddings + pgvector on RDS.

## Configuration matrix
| Concern | Local default | Cloud |
|---|---|---|
| Database | SQLite `backend/data/local.db` | `DATABASE_URL` → RDS |
| Storage | `backend/data/storage` | `AWS_S3_BUCKET` → S3 (IAM role) |
| Processing | background task | `LOCAL_PROCESSING=false` → Lambda |
| AI | `AI_PROVIDER=groq` (or `mock`) | same |

## Production hardening roadmap
- Authentication and per-user libraries (Amazon Cognito); add `user_id` to `papers`.
- SQS queue between upload and Lambda for rate-limit-aware retries and a dead-letter queue.
- OCR fallback with Amazon Textract.
- Secrets in AWS Secrets Manager; Alembic migrations; CloudWatch alarms.
- Embedding-based retrieval (pgvector) and citation graphs.
