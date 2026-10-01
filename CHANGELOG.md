# Changelog

## 2.0.0 — Enhanced release

### Fixed (gaps in 1.0)
- S3 was only used when access keys were set, so EC2/Lambda with an IAM role silently fell back to local disk.
- Uploaded filenames were used directly in storage paths (path traversal risk). Now sanitised.
- Inline mode blocked the upload request until the AI finished. Now a true background task.
- Only the first 12,000 characters reached the AI; conclusions were usually lost. Now head + conclusion, references removed.
- `.env` was loaded after the shared package read its settings.
- CORS combined `allow_origins=["*"]` with credentials. Now explicit origins.
- Deleting a paper left its files in S3 / on disk. IAM policy lacked `s3:DeleteObject`.
- `.PDF` (uppercase) files produced wrong output paths.
- No upload size limit or real PDF check. Added both.
- Papers could stay "processing" forever after a server restart. Now auto-marked as failed on startup.
- Lambda in a VPC could not reach the Groq API (no NAT) — documented with a fix; timeout raised 60s → 180s.
- Lambda S3 event keys were not URL-decoded.
- The list view never refreshed while papers were processing.
- The docs promised drag & drop, but the UI had none.
- Frontend crashed silently when the backend was offline.

### Added
- Real related papers from arXiv (verified, with links) alongside labelled AI suggestions.
- "Ask the paper" Q&A with visible source passages.
- Multi-paper comparison with research gaps and reading order.
- TL;DR, detected title, difficulty, page/word counts, processing time, model used.
- Search, Markdown export, open original PDF, re-run AI, toast notifications, system-status panel.
- AI retries with back-off on rate limits; JSON mode for reliable output.
- Mock AI provider (run and test without any key).
- 10 automated tests, GitHub Actions CI, Makefile, sample PDF, multi-stage Dockerfile serving API + UI, Postgres health-check in Compose.
- Consolidated AWS deployment guide (two tiers, cost notes, HTTPS via CloudFront).
