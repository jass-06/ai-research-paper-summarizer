"""AWS Lambda entry point for serverless paper processing (v2).

Triggers handled:
  1. Direct async invoke from the backend: {"paper_id": ..., "s3_key": ...}
  2. S3 "ObjectCreated" event on the uploads/ prefix.
     WARNING: enable only ONE of the two triggers, otherwise every paper is
     processed twice (double AI cost). The backend uses (1) by default.

It runs exactly the same `shared.pipeline.run()` as the backend's inline mode,
then updates the papers row in RDS PostgreSQL (Lambda must be in the RDS VPC).

Required env vars: AWS_S3_BUCKET, DATABASE_URL, GROQ_API_KEY
build.sh copies the repo's shared/ package into the zip, and sets
STORAGE_BACKEND=s3 via the deploy script.
"""
import json
import os
import re
import urllib.parse

import psycopg2

os.environ.setdefault("STORAGE_BACKEND", "s3")
from shared import pipeline  # noqa: E402  (copied in by build.sh)

DATABASE_URL = os.environ["DATABASE_URL"]  # postgresql://user:pass@rds-endpoint:5432/dbname
JSON_FIELDS = {"keywords", "topics", "related_papers"}


def _update_paper(paper_id: str, **fields):
    if not fields:
        return
    cols, values = [], []
    for key, val in fields.items():
        if key in JSON_FIELDS:
            cols.append(f"{key} = %s::json")
            values.append(json.dumps(val))
        else:
            cols.append(f"{key} = %s")
            values.append(val)
    sql = f"UPDATE papers SET {', '.join(cols)}, updated_at = NOW() WHERE id = %s"
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, values + [paper_id])
    finally:
        conn.close()


def _from_s3_record(record):
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])  # S3 URL-encodes keys
    match = re.search(r"uploads/[^/]+/([0-9a-fA-F-]{36})_", key)
    return (match.group(1) if match else None), key


def lambda_handler(event, context):
    jobs = []
    if "Records" in event:
        for record in event["Records"]:
            paper_id, key = _from_s3_record(record)
            if paper_id:
                jobs.append((paper_id, key))
    else:
        jobs.append((event["paper_id"], event["s3_key"]))

    results = [_process_one(pid, key) for pid, key in jobs]
    print(json.dumps({"processed": results}))  # visible in CloudWatch Logs
    return {"statusCode": 200, "body": json.dumps(results)}


def _process_one(paper_id: str, s3_key: str) -> dict:
    try:
        _update_paper(paper_id, status="processing")
        fields = pipeline.run(s3_key)
        _update_paper(paper_id, status="done", error_message=None, **fields)
        return {"paper_id": paper_id, "status": "done"}
    except pipeline.NoTextError as exc:
        _update_paper(paper_id, status="error", error_message=str(exc))
        return {"paper_id": paper_id, "status": "error", "reason": "no_text"}
    except Exception as exc:  # log and move on; never crash the whole invocation
        try:
            _update_paper(paper_id, status="error", error_message=str(exc)[:2000])
        except Exception:
            pass
        return {"paper_id": paper_id, "status": "error", "reason": str(exc)[:300]}
