"""IBM Cloud Object Storage-based state persistence for IBM Cloud Functions deployment.

Replaces local file-based state.py with IBM Cloud Object Storage for tracking seen articles.
Falls back to local file storage if COS is not configured (for local development).

Environment variables required:
  - IBM_COS_BUCKET: IBM Cloud Object Storage bucket name for state storage
  - IBM_COS_ENDPOINT: COS endpoint URL (e.g., s3.us-south.cloud-object-storage.appdomain.cloud)
  - IBM_COS_API_KEY: IBM Cloud API key with COS access
  - IBM_COS_INSTANCE_CRN: COS service instance CRN
  
The state file is stored at: cos://{bucket}/state/seen_articles.json
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


def _use_cos() -> bool:
    """Check if IBM Cloud Object Storage should be used (based on environment variable)."""
    return bool(os.getenv("IBM_COS_BUCKET"))


def _get_cos_client():
    """Get IBM Cloud Object Storage client. Lazy import to avoid dependency in local mode."""
    try:
        import ibm_boto3
        from ibm_botocore.client import Config
        
        api_key = os.getenv("IBM_COS_API_KEY")
        instance_crn = os.getenv("IBM_COS_INSTANCE_CRN")
        endpoint = os.getenv("IBM_COS_ENDPOINT")
        
        if not all([api_key, instance_crn, endpoint]):
            raise RuntimeError(
                "IBM Cloud Object Storage not fully configured. Required environment variables: "
                "IBM_COS_API_KEY, IBM_COS_INSTANCE_CRN, IBM_COS_ENDPOINT"
            )
        
        return ibm_boto3.client(
            "s3",
            ibm_api_key_id=api_key,
            ibm_service_instance_id=instance_crn,
            config=Config(signature_version="oauth"),
            endpoint_url=endpoint
        )
    except ImportError as exc:
        raise RuntimeError(
            "ibm-cos-sdk is required for IBM Cloud Object Storage. "
            "Install with: pip install ibm-cos-sdk"
        ) from exc


def _cos_key() -> str:
    """COS object key for the state file."""
    return "state/seen_articles.json"


def _local_path() -> Path:
    """Fallback local path for development/testing."""
    from . import config
    rel = _state_cfg().get("seen_file", "output/seen_articles.json")
    return config.ROOT / rel


def load_seen() -> dict[str, str]:
    """Load seen articles state. Returns {link: iso_date_first_seen}."""
    if _use_cos():
        return _load_from_cos()
    return _load_from_local()


def _load_from_cos() -> dict[str, str]:
    """Load state from IBM Cloud Object Storage."""
    bucket = os.getenv("IBM_COS_BUCKET")
    key = _cos_key()
    
    try:
        cos = _get_cos_client()
        response = cos.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        logger.info(f"Loaded state from cos://{bucket}/{key}")
        return json.loads(content)
    except cos.exceptions.NoSuchKey:
        logger.info(f"No existing state found at cos://{bucket}/{key}, starting fresh")
        return {}
    except Exception as exc:
        logger.error(f"Failed to load state from IBM Cloud Object Storage: {exc}")
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
    
    if _use_cos():
        _save_to_cos(pruned)
    else:
        _save_to_local(pruned)


def _save_to_cos(seen: dict[str, str]) -> None:
    """Save state to IBM Cloud Object Storage."""
    bucket = os.getenv("IBM_COS_BUCKET")
    key = _cos_key()
    
    try:
        cos = _get_cos_client()
        content = json.dumps(seen, indent=2)
        cos.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="application/json"
        )
        logger.info(f"Saved state to cos://{bucket}/{key} ({len(seen)} entries)")
    except Exception as exc:
        logger.error(f"Failed to save state to IBM Cloud Object Storage: {exc}")
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
