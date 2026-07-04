"""S3-based state persistence for AWS Lambda deployment.

Replaces local file-based state.py with S3 storage for tracking seen articles.
Falls back to local file storage if S3 is not configured (for local development).

Environment variables required:
  - AWS_S3_BUCKET: S3 bucket name for state storage
  - AWS_REGION: AWS region (optional, defaults to us-east-1)
  
The state file is stored at: s3://{bucket}/state/seen_articles.json
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _state_cfg() -> dict:
    """Get state configuration from settings."""
    from . import config
    return config.settings().get("state", {})


def _use_s3() -> bool:
    """Check if S3 storage should be used (based on environment variable)."""
    return bool(os.getenv("AWS_S3_BUCKET"))


def _get_s3_client():
    """Get boto3 S3 client. Lazy import to avoid dependency in local mode."""
    try:
        import boto3
        region = os.getenv("AWS_REGION", "us-east-1")
        return boto3.client("s3", region_name=region)
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for S3 state storage. Install with: pip install boto3"
        ) from exc


def _s3_key() -> str:
    """S3 object key for the state file."""
    return "state/seen_articles.json"


def _local_path() -> Path:
    """Fallback local path for development/testing."""
    from . import config
    rel = _state_cfg().get("seen_file", "output/seen_articles.json")
    return config.ROOT / rel


def load_seen() -> dict[str, str]:
    """Load seen articles state. Returns {link: iso_date_first_seen}."""
    if _use_s3():
        return _load_from_s3()
    return _load_from_local()


def _load_from_s3() -> dict[str, str]:
    """Load state from S3."""
    bucket = os.getenv("AWS_S3_BUCKET")
    key = _s3_key()
    
    try:
        s3 = _get_s3_client()
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        logger.info(f"Loaded state from s3://{bucket}/{key}")
        return json.loads(content)
    except s3.exceptions.NoSuchKey:
        logger.info(f"No existing state found at s3://{bucket}/{key}, starting fresh")
        return {}
    except Exception as exc:
        logger.error(f"Failed to load state from S3: {exc}")
        return {}


def _load_from_local() -> dict[str, str]:
    """Load state from local file (development fallback)."""
    path = _local_path()
    if not path.exists():
        logger.info(f"No local state file at {path}, starting fresh")
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        logger.info(f"Loaded state from local file: {path}")
        return json.loads(content)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"Failed to load local state: {exc}")
        return {}


def save_seen(seen: dict[str, str]) -> None:
    """Save seen articles state (pruned automatically)."""
    pruned = prune(seen)
    
    if _use_s3():
        _save_to_s3(pruned)
    else:
        _save_to_local(pruned)


def _save_to_s3(seen: dict[str, str]) -> None:
    """Save state to S3."""
    bucket = os.getenv("AWS_S3_BUCKET")
    key = _s3_key()
    
    try:
        s3 = _get_s3_client()
        content = json.dumps(seen, indent=2)
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="application/json"
        )
        logger.info(f"Saved state to s3://{bucket}/{key} ({len(seen)} entries)")
    except Exception as exc:
        logger.error(f"Failed to save state to S3: {exc}")
        raise


def _save_to_local(seen: dict[str, str]) -> None:
    """Save state to local file (development fallback)."""
    path = _local_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(seen, indent=2)
    path.write_text(content, encoding="utf-8")
    logger.info(f"Saved state to local file: {path} ({len(seen)} entries)")


def prune(seen: dict[str, str]) -> dict[str, str]:
    """Remove entries older than retention period."""
    days = int(_state_cfg().get("seen_retention_days", 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    kept: dict[str, str] = {}
    pruned_count = 0
    
    for link, iso in seen.items():
        try:
            seen_dt = datetime.fromisoformat(iso)
            if seen_dt.tzinfo is None:
                seen_dt = seen_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pruned_count += 1
            continue
            
        if seen_dt >= cutoff:
            kept[link] = iso
        else:
            pruned_count += 1
    
    if pruned_count > 0:
        logger.info(f"Pruned {pruned_count} old entries (retention: {days} days)")
    
    return kept


def mark_seen(seen: dict[str, str], links: list[str]) -> dict[str, str]:
    """Mark links as seen (preserves original first-seen timestamp)."""
    today = datetime.now(timezone.utc).isoformat()
    new_count = 0
    
    for link in links:
        if link not in seen:
            seen[link] = today
            new_count += 1
    
    if new_count > 0:
        logger.info(f"Marked {new_count} new article(s) as seen")
    
    return seen
