"""RSS feed fetching via Google News.

We build Google News RSS *search* URLs from each account's primary query terms
(entity names + subsidiaries). No manual Google Alerts setup is required —
Google News exposes an RSS endpoint for any search query:

    https://news.google.com/rss/search?q=<query>&hl=en-CA&gl=CA&ceid=CA:en

Each returned entry is normalised into an `Article` dataclass and filtered to
the recency window defined in settings.yaml (feeds.max_age_hours).
"""
from __future__ import annotations

import base64
import binascii
import re
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone

import feedparser
from dateutil import parser as dateparser

from . import config


@dataclass
class Article:
    account: str                 # account key (JDI / IOL / GNB)
    account_label: str
    query: str                   # the search term that surfaced it
    title: str
    link: str
    source: str                  # publisher name
    summary: str
    published: datetime | None   # tz-aware UTC
    # populated later by the filter:
    score: int = 0
    matched_terms: list[str] = field(default_factory=list)
    trigger_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published"] = self.published.isoformat() if self.published else None
        return d


GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def _build_url(query: str) -> str:
    s = config.settings()["feeds"]
    # Quote the phrase so Google treats multi-word entity names as a unit.
    q = f'"{query}"' if " " in query else query
    params = {
        "q": q,
        "hl": f'{s["language"]}-{s["country"]}',
        "gl": s["country"],
        "ceid": f'{s["country"]}:{s["language"]}',
    }
    return f"{GOOGLE_NEWS_RSS}?{urllib.parse.urlencode(params)}"


def _search_url(title: str, source: str = "") -> str:
    """A Google search link for the headline — ALWAYS resolves to the article.

    Used as a guaranteed-working fallback when we can't extract a direct
    publisher URL from the opaque Google News link.
    """
    q = urllib.parse.quote_plus(f"{title} {source}".strip())
    return f"https://www.google.com/search?q={q}"


def _valid_article_url(u: str) -> bool:
    """A real-looking external article URL (not Google, has a domain + TLD)."""
    if not u or len(u) > 600:
        return False
    if not re.match(r"https?://[\w.-]+\.[a-z]{2,}(?:[:/]|$)", u, re.I):
        return False
    return "google.com" not in u.split("/")[2].lower()


def _decode_gnews_url(url: str) -> str | None:
    """Best-effort decode of a Google News /articles/<base64> link to the real
    publisher URL. Works for the common encoding without any network call.
    Returns None if it can't confidently extract a valid publisher URL.
    """
    m = re.search(r"/articles/([^?/]+)", url)
    if not m:
        return None
    seg = m.group(1)
    seg += "=" * (-len(seg) % 4)               # fix base64 padding
    try:
        raw = base64.urlsafe_b64decode(seg)
    except (binascii.Error, ValueError):
        return None
    text = raw.decode("latin-1", errors="ignore")
    for cand in re.findall(r"https?://[^\s\"'\\<>]+", text):
        # Trim trailing protobuf/control junk: keep up to the last alphanumeric
        # or '/' so we don't leave stray bytes (e.g. '@', '\x01') on the URL.
        cand = re.sub(r"[^A-Za-z0-9/]+$", "", cand)
        if _valid_article_url(cand):
            return cand
    return None


def _resolve_link(url: str, title: str, source: str = "") -> str:
    """Return a link that ALWAYS works.

    1. Direct publisher link (feed already gave one) -> use as-is.
    2. Google News link we can decode -> the real publisher URL.
    3. Otherwise -> a Google search link for the headline (never breaks).
    """
    url = (url or "").strip()
    if url and "news.google.com" not in url and _valid_article_url(url):
        return url
    if "news.google.com" in url:
        decoded = _decode_gnews_url(url)
        if decoded:
            return decoded
    return _search_url(title, source)


def _parse_date(entry) -> datetime | None:
    """Return a tz-aware UTC datetime for a feed entry, or None."""
    # feedparser exposes a parsed struct_time when it can.
    if getattr(entry, "published_parsed", None):
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw:
        try:
            dt = dateparser.parse(raw)
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc) if dt else None
        except (ValueError, OverflowError):
            return None
    return None


def _primary_queries() -> list[tuple[str, str, str]]:
    """Yield (account_key, account_label, query_term) for every primary term."""
    out: list[tuple[str, str, str]] = []
    for key, acct in config.keywords()["accounts"].items():
        label = acct["label"]
        for term in acct.get("entity_names", []) + acct.get("subsidiaries", []):
            out.append((key, label, term))
    return out


def fetch_all(verbose: bool = True) -> list[Article]:
    """Fetch every primary query, normalise, dedupe, and recency-filter."""
    s = config.settings()["feeds"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=s["max_age_hours"])
    delay = s.get("request_delay_seconds", 1.0)
    per_query = s.get("max_items_per_query", 25)

    seen_links: set[str] = set()
    articles: list[Article] = []

    for key, label, term in _primary_queries():
        url = _build_url(term)
        feed = feedparser.parse(url)
        if verbose:
            print(f"  [{key}] '{term}': {len(feed.entries)} entries")

        for entry in feed.entries[:per_query]:
            raw_link = getattr(entry, "link", "").strip()
            if not raw_link or raw_link in seen_links:
                continue
            published = _parse_date(entry)
            # Recency gate — drop anything older than the window or undated.
            if published is None or published < cutoff:
                continue
            seen_links.add(raw_link)

            # Google News appends " - Publisher" to titles; split it out.
            raw_title = getattr(entry, "title", "").strip()
            source = ""
            if " - " in raw_title:
                raw_title, source = raw_title.rsplit(" - ", 1)
            source = getattr(getattr(entry, "source", None), "title", source)

            # Resolve to a link that ALWAYS works (publisher URL or search link).
            link = _resolve_link(raw_link, raw_title, source)

            articles.append(
                Article(
                    account=key,
                    account_label=label,
                    query=term,
                    title=raw_title,
                    link=link,
                    source=source or "Unknown",
                    summary=_strip_html(getattr(entry, "summary", "")),
                    published=published,
                )
            )
        time.sleep(delay)

    if verbose:
        print(f"  -> {len(articles)} unique articles within {s['max_age_hours']}h window")
    return articles


def _strip_html(text: str) -> str:
    """Very light HTML strip for feed summaries (avoids extra deps)."""
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


if __name__ == "__main__":
    for a in fetch_all():
        print(f"[{a.account}] {a.published:%Y-%m-%d %H:%M} | {a.title} ({a.source})")
