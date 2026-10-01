"""Storage abstraction: Amazon S3 or local disk, chosen by env vars only.

STORAGE_BACKEND = auto (default) | s3 | local
  auto -> S3 if AWS_S3_BUCKET is set, otherwise local disk.

Fix vs v1: v1 only used S3 when AWS_ACCESS_KEY_ID was set, so on EC2/Lambda
with an IAM *role* (the recommended, key-less setup) it silently fell back to
local disk. We now use boto3's default credential chain (env keys, ~/.aws,
instance role, Lambda role) — whichever exists.
"""
from __future__ import annotations

import os
import re
from pathlib import Path


def backend() -> str:
    choice = os.environ.get("STORAGE_BACKEND", "auto").strip().lower()
    if choice in ("s3", "local"):
        return choice
    return "s3" if os.environ.get("AWS_S3_BUCKET") else "local"


def is_cloud_storage() -> bool:
    return backend() == "s3"


def _local_root() -> Path:
    return Path(os.environ.get("LOCAL_STORAGE_DIR", "./local_storage")).resolve()


def _local_path(key: str) -> Path:
    root = _local_root()
    path = (root / key).resolve()
    if root not in path.parents:  # defence in depth against ../ in keys
        raise ValueError("Invalid storage key")
    return path


_client = None


def _s3():
    global _client
    if _client is None:
        import boto3  # imported lazily so local mode never needs AWS libs configured
        _client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _client


def _bucket() -> str:
    bucket = os.environ.get("AWS_S3_BUCKET")
    if not bucket:
        raise RuntimeError("STORAGE_BACKEND=s3 but AWS_S3_BUCKET is not set")
    return bucket


def safe_filename(name: str) -> str:
    """Strip directories and odd characters: '../../etc/x.pdf' -> 'x.pdf'."""
    name = os.path.basename(name.replace("\\", "/"))
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .") or "paper.pdf"
    return name[:150]


def put_object(key: str, content: bytes, content_type: str = "application/octet-stream") -> str:
    if is_cloud_storage():
        _s3().put_object(Bucket=_bucket(), Key=key, Body=content, ContentType=content_type)
        return key
    path = _local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return key


def get_object(key: str) -> bytes:
    if is_cloud_storage():
        return _s3().get_object(Bucket=_bucket(), Key=key)["Body"].read()
    return _local_path(key).read_bytes()


def delete_object(key: str | None) -> None:
    """Deletes quietly — a missing object is not an error (v1 never deleted files at all)."""
    if not key:
        return
    try:
        if is_cloud_storage():
            _s3().delete_object(Bucket=_bucket(), Key=key)
        else:
            p = _local_path(key)
            if p.exists():
                p.unlink()
    except Exception:
        pass


def presigned_url(key: str, expires: int = 900) -> str | None:
    """Temporary download link for S3 objects (None in local mode)."""
    if not is_cloud_storage():
        return None
    return _s3().generate_presigned_url(
        "get_object", Params={"Bucket": _bucket(), "Key": key}, ExpiresIn=expires
    )
