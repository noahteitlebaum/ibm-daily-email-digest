"""Relevance scoring and guardrail filtering for the daily digest.

Google News RSS gives thin metadata (the <description> is essentially the title
repeated), so matching is title-driven and built to be robust:

  * full-phrase matches for entity/subsidiary names, people, tech signals
  * distinctive-token matches (e.g. "Canaport", "Cavendish", "FCCU") so an
    article isn't missed just because a headline abbreviates a name
  * dollar-figure / capex detection (e.g. "$100M", "C$450 million")
  * credit for the search query that surfaced the article (account association)

Guardrails from keywords.yaml are applied:
  * require_irving_qualifier  -> drop bare-"Irving" matches with no qualifier
  * exclude_terms             -> drop out-of-scope items (e.g. Irving Shipbuilding)
  * gnb_max_items             -> cap the noisier GNB feed

An article is kept only if it is BOTH associated with an account AND carries at
least one opportunity signal (trigger / tech / person / strong-name), and its
weighted score clears settings.filtering.min_relevance_score.
"""
from __future__ import annotations

import html
import re

from . import config
from .feeds import Article

# Generic tokens that must NOT be used as standalone "distinctive" evidence
# (they appear in unrelated New Brunswick / general news).
_GENERIC_TOKENS = {
    "irving", "new", "brunswick", "news", "limited", "ltd", "province",
    "government", "service", "atlantic", "building", "supplies", "consumer",
    "products", "transport", "midland", "digital", "opportunities", "oil",
    "saint", "john", "of", "the", "and", "for", "co", "inc", "company",
    "kent", "horizon", "health", "network",
    # Generic words from the expanded GNB departments / crown corps / munis
    # (2026-07-22). These must NOT stand alone as distinctive evidence, or
    # unrelated NB news matches. The full phrases (e.g. "NB Power", "City of
    # Moncton") still match via _contains, and proper nouns (Moncton,
    # Fredericton, ANBL, WorkSafeNB, Vestcor, Lepreau, Mactaquac, ...) are
    # deliberately left OUT so they remain valid distinctive tokens.
    "department", "education", "early", "childhood", "justice", "public",
    "safety", "transportation", "infrastructure", "finance", "treasury",
    "board", "secondary", "training", "labour", "natural", "resources",
    "energy", "development", "local", "social", "post", "power", "liquor",
    "cannabis", "housing", "corporation", "financial", "services",
    "commission", "ambulance", "city", "town",
}

# Regex for capital-figure signals: $100M, C$450 million, US$600M, 1.3B, etc.
_MONEY_RE = re.compile(
    r"(?:US?\$|C\$|CAD|USD|\$)\s?\d[\d,.]*\s?(?:million|billion|m|b)\b"
    r"|\b\d[\d,.]*\s?(?:million|billion)\b",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return html.unescape(text or "").lower()


def _contains(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack


def _distinctive_tokens(phrases: list[str]) -> set[str]:
    """Pull non-generic tokens (len>=4) from a list of names for loose matching."""
    toks: set[str] = set()
    for phrase in phrases:
        for tok in re.split(r"[^a-zA-Z]+", phrase.lower()):
            if len(tok) >= 4 and tok not in _GENERIC_TOKENS:
                toks.add(tok)
    return toks


def _score_article(article: Article) -> Article:
    s = config.settings()["filtering"]
    w = s["weights"]
    acct = config.keywords()["accounts"][article.account]

    title = _clean(article.title)
    summary = _clean(article.summary)
    blob = f"{title} {summary}"

    score = 0
    matched: list[str] = []
    triggers: list[str] = []
    has_account_evidence = False     # any association, incl. the surfacing query
    has_content_account = False      # the TEXT actually references the account
    has_opportunity_signal = False

    def credit(terms, weight, kind, *, account_ev=False, opp=False):
        nonlocal score, has_account_evidence, has_content_account, has_opportunity_signal
        for term in terms:
            if _contains(blob, term):
                score += weight
                if _contains(title, term):
                    score += w["title_bonus"]
                matched.append(f"{term} ({kind})")
                if account_ev:
                    has_account_evidence = True
                    has_content_account = True   # real in-text account reference
                if opp:
                    has_opportunity_signal = True

    credit(acct.get("entity_names", []), w["entity_name"], "entity", account_ev=True)
    credit(acct.get("subsidiaries", []), w["subsidiary"], "subsidiary",
           account_ev=True, opp=True)
    credit(acct.get("people", []), w["person"], "person",
           account_ev=True, opp=True)
    credit(acct.get("tech_signals", []), w["tech_signal"], "tech",
           account_ev=True, opp=True)
    credit(acct.get("industry_terms", []), w["industry_term"], "industry",
           account_ev=True)

    # Distinctive single-token matches (e.g. "canaport", "cavendish", "whitegate").
    names = acct.get("entity_names", []) + acct.get("subsidiaries", [])
    for tok in _distinctive_tokens(names):
        if re.search(rf"\b{re.escape(tok)}\b", blob):
            score += w["subsidiary"]
            if re.search(rf"\b{re.escape(tok)}\b", title):
                score += w["title_bonus"]
            matched.append(f"{tok} (name-token)")
            has_account_evidence = True
            has_content_account = True

    # The query that surfaced the article is WEAK association only — it does NOT
    # count as the article being about the account (avoids generic NB news pulled
    # by a broad subsidiary query being mislabelled to that account).
    if article.query:
        has_account_evidence = True
        score += 1
        matched.append(f"{article.query} (query)")

    # Trigger events (compelling reasons to act).
    for trig_type, phrases in s["trigger_events"].items():
        for phrase in phrases:
            if _contains(blob, phrase):
                score += w["trigger_event"]
                if trig_type not in triggers:
                    triggers.append(trig_type)
                has_opportunity_signal = True
                break

    # Dollar-figure / capex signal.
    if _MONEY_RE.search(blob):
        score += w["trigger_event"]
        if "capex" not in triggers:
            triggers.append("capex")
        has_opportunity_signal = True
        matched.append("$ figure (capex)")

    article.score = score
    article.matched_terms = matched
    article.trigger_types = triggers
    # Stash gate flags on the object for the keep decision.
    article._account_ev = has_account_evidence       # type: ignore[attr-defined]
    article._content_account_ev = has_content_account  # type: ignore[attr-defined]
    article._opp_signal = has_opportunity_signal      # type: ignore[attr-defined]
    return article


def _passes_guardrails(article: Article) -> bool:
    c = config.keywords().get("cautions", {})
    blob = _clean(f"{article.title} {article.summary}")

    for term in c.get("exclude_terms", []):
        if _contains(blob, term):
            return False

    if c.get("require_irving_qualifier", False) and "irving" in blob:
        qualifiers = [
            "irving oil", "j.d. irving", "jd irving", "j. d. irving",
            "irving limited", "irving tissue", "irving woodlands",
            "irving consumer", "irving pulp", "irving forestry",
            "irving logistics", "irving personal care", "irving green",
            "saint john refinery", "canaport", "cavendish", "kent building",
            "midland transport", "brunswick news", "irving paper",
        ]
        if not any(q in blob for q in qualifiers):
            return False

    return True


def filter_articles(articles: list[Article], verbose: bool = True) -> list[Article]:
    s = config.settings()["filtering"]
    min_score = s["min_relevance_score"]
    gnb_cap = config.keywords().get("cautions", {}).get("gnb_max_items", 8)

    kept: list[Article] = []
    for art in articles:
        if not _passes_guardrails(art):
            continue
        _score_article(art)
        # Must genuinely reference the account in its TEXT (not just be returned
        # by the query) AND carry an opportunity signal AND clear the score.
        if (getattr(art, "_content_account_ev", False)
                and getattr(art, "_opp_signal", False)
                and art.score >= min_score):
            kept.append(art)

    kept.sort(key=lambda a: a.score, reverse=True)

    gnb = [a for a in kept if a.account == "GNB"][:gnb_cap]
    others = [a for a in kept if a.account != "GNB"]
    result = sorted(others + gnb, key=lambda a: a.score, reverse=True)

    if verbose:
        print(f"  -> {len(result)} relevant articles (min score {min_score})")
    return result


def account_context(articles: list[Article], top_n: int = 6,
                    verbose: bool = True) -> list[Article]:
    """Articles that are *about* an account but didn't meet the opportunity bar.

    Used as a daily fallback ("account radar") so the digest is never empty even
    when there are no opportunity-grade signals in the news.
    """
    gnb_cap = config.keywords().get("cautions", {}).get("gnb_max_items", 8)
    pool: list[Article] = []
    for art in articles:
        if not _passes_guardrails(art):
            continue
        _score_article(art)
        # Radar only includes articles that actually reference the account in
        # their text — not generic news pulled in by a broad query.
        if getattr(art, "_content_account_ev", False):
            pool.append(art)
    pool.sort(key=lambda a: a.score, reverse=True)
    gnb = [a for a in pool if a.account == "GNB"][:gnb_cap]
    others = [a for a in pool if a.account != "GNB"]
    result = sorted(others + gnb, key=lambda a: a.score, reverse=True)[:top_n]
    if verbose:
        print(f"  -> {len(result)} account-radar article(s) (context fallback)")
    return result
