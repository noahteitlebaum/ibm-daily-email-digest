"""Cross-run state: remember which articles we've already surfaced.

Persists a small JSON map of  article-link -> ISO-date-first-seen  so each daily
run can distinguish genuinely NEW opportunities from ones carried over inside the
7-day window. Entries older than the retention period are pruned automatically.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config


def _state_cfg() -> dict:
    return config.settings().get("state", {})


def _seen_path() -> Path:
    rel = _state_cfg().get("seen_file", "output/seen_articles.json")
    return config.ROOT / rel


def load_seen() -> dict[str, str]:
    """Return {link: iso_date_first_seen}. Empty dict if no file yet."""
    path = _seen_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def prune(seen: dict[str, str]) -> dict[str, str]:
    """Drop entries older than seen_retention_days."""
    days = int(_state_cfg().get("seen_retention_days", 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    kept: dict[str, str] = {}
    for link, iso in seen.items():
        try:
            seen_dt = datetime.fromisoformat(iso)
            if seen_dt.tzinfo is None:
                seen_dt = seen_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if seen_dt >= cutoff:
            kept[link] = iso
    return kept


def save_seen(seen: dict[str, str]) -> None:
    path = _seen_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prune(seen), indent=2), encoding="utf-8")


def mark_seen(seen: dict[str, str], links) -> dict[str, str]:
    """Record links as seen as of now (does not overwrite an earlier first-seen)."""
    today = datetime.now(timezone.utc).isoformat()
    for link in links:
        seen.setdefault(link, today)
    return seen
