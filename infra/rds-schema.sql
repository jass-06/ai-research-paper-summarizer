-- PostgreSQL schema for the `papers` table (v2).
-- The backend also creates/updates this automatically on startup (init_db),
-- so running this file manually is optional.

CREATE TABLE IF NOT EXISTS papers (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_filename  VARCHAR(255) NOT NULL,
    s3_pdf_path        VARCHAR(512) NOT NULL,
    s3_output_path     VARCHAR(512),
    text_path          VARCHAR(512),            -- extracted full text (used by "Ask the paper")

    status             VARCHAR(20)  NOT NULL DEFAULT 'uploaded',  -- uploaded | processing | done | error

    title              VARCHAR(500),            -- real title detected by the AI
    tldr               TEXT,                    -- one-sentence plain-English summary
    summary            TEXT,
    keywords           JSON,
    topics             JSON,
    related_papers     JSON,                    -- [{title, reason, url?, authors?, year?, source, verified}]
    difficulty         VARCHAR(20),             -- introductory | intermediate | advanced
    notes              TEXT DEFAULT '',
    error_message      TEXT,

    page_count         INTEGER,
    word_count         INTEGER,
    file_size_bytes    INTEGER,
    model_used         VARCHAR(100),
    processing_seconds DOUBLE PRECISION,

    created_at         TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_papers_status     ON papers (status);
CREATE INDEX IF NOT EXISTS idx_papers_created_at ON papers (created_at DESC);
