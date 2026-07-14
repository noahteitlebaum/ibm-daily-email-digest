"""Configuration loading for the IBM Daily Email Digest.

Loads YAML config (keywords + settings) and environment secrets (.env).
Keeping all path resolution here means every other module can stay
location-agnostic.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Project root = parent of this src/ directory.
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

# Load .env once on import (no error if missing — env vars may be set elsewhere).
load_dotenv(ROOT / ".env")


@lru_cache(maxsize=1)
def keywords() -> dict[str, Any]:
    """Account keyword definitions (config/keywords.yaml)."""
    with open(CONFIG_DIR / "keywords.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def teams() -> list[dict[str, Any]]:
    """Recipient teams (config/teams.yaml). Each: name, recipients, accounts,
    grounding. Empty list if the file is absent (falls back to single-team)."""
    path = CONFIG_DIR / "teams.yaml"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    tlist = data.get("teams", [])
    # Recipients come from RECIPIENTS_<ID> in .env / GitHub secrets (keeps
    # addresses out of the committed repo). Fall back to the yaml list.
    for t in tlist:
        tid = t.get("id")
        if tid:
            raw = os.getenv(f"RECIPIENTS_{tid.upper()}")
            if raw:
                t["recipients"] = [r.strip() for r in raw.split(",") if r.strip()]
    return tlist


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    """General settings (config/settings.yaml)."""
    with open(CONFIG_DIR / "settings.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def env(name: str, default: str | None = None) -> str | None:
    """Read an environment variable (loaded from .env)."""
    return os.getenv(name, default)


def grounding_text() -> str:
    """Return the full text of the grounding knowledge base."""
    rel = settings()["summarization"]["grounding_file"]
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(
            f"Grounding file not found at {path}. Check settings.yaml "
            "-> summarization.grounding_file."
        )
    return path.read_text(encoding="utf-8")


def grounding_for(account_keys) -> str:
    """Concatenate the grounding briefs for the given account keys.

    Each account in keywords.yaml may declare `grounding_file: <path>`. This
    joins the unique existing briefs for the accounts a team covers. Returns ""
    if none of the accounts have a brief (news-only framing for that team).
    """
    accounts = keywords().get("accounts", {})
    seen_files: set[str] = set()
    parts: list[str] = []
    for key in account_keys:
        rel = (accounts.get(key) or {}).get("grounding_file")
        if not rel or rel in seen_files:
            continue
        path = ROOT / rel
        if path.exists():
            seen_files.add(rel)
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


def product_hierarchy_text() -> str:
    """Return the IBM product taxonomy text (empty string if not configured)."""
    rel = settings()["summarization"].get("product_hierarchy_file")
    if not rel:
        return ""
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def advisor_text() -> str:
    """Return the advisor writing-style spec (ADVISOR_INSTRUCTIONS.md), or ''.

    Controlled by settings.summarization.advisor_style_file (default the repo-root
    ADVISOR_INSTRUCTIONS.md). Empty string disables it.
    """
    rel = settings().get("summarization", {}).get(
        "advisor_style_file", "ADVISOR_INSTRUCTIONS.md")
    if not rel:
        return ""
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def output_dir() -> Path:
    """Resolve (and create) the output directory."""
    # In Lambda, use /tmp (only writable directory); locally use configured path
    if os.getenv("AWS_EXECUTION_ENV"):  # Running in Lambda
        d = Path("/tmp/output")
    else:
        d = ROOT / settings()["output"]["base_dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d
