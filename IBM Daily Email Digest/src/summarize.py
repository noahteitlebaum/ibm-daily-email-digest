"""Summarization engine.

Feeds the filtered articles + the grounding knowledge base to the LLM (ICA)
and asks for a structured digest. The model must return JSON so we can render
both the email and the decks deterministically.

Required framing (per project spec + grounding doc):
  * TLDR              — one-paragraph executive summary of the whole digest
  * Three Whys        — Why anything? / Why now? / Why IBM?
  * CEM stage         — which Client Engagement Model sales stage the event implies
  * MEDDPICC          — which fields the news helps qualify vs. which stay open
"""
from __future__ import annotations

import json
import re

from . import config
from .feeds import Article
from .llm_client import LLMClient

SYSTEM_PROMPT = """\
You are an IBM Technology Sales analyst on the Horizon Atlantic account team.
You convert client news into IBM sales-opportunity insights using ONLY the
grounding knowledge base provided and the news items supplied. You are precise,
commercially minded, and you never invent contacts, dollar figures, or contract
terms that are not in the grounding doc or the news item.

Hard guardrails (always apply):
- Never pitch net-new QRadar/SIEM — IBM exited SIEM. Security plays = data
  security, cyber recovery, identity, assessment (SaRA).
- For J.D. Irving: complement Aera Technology (do not position watsonx as a
  displacement); do not pitch a conflicting story for Kent (committed to MS D365).
- Separate fact (from the article) from inference (your mapping). Mark confidence.
- Tie every insight to a CEM stage and a concrete next move.
- Government of New Brunswick has no dedicated account brief: treat specific
  contacts/contracts as "to validate" and do not fabricate them.
"""

USER_TEMPLATE = """\
=== GROUNDING KNOWLEDGE BASE (authoritative background) ===
{grounding}

=== IBM PRODUCT TAXONOMY (map every offering to a canonical product + code here) ===
{product_hierarchy}

=== TODAY'S NEWS ITEMS (new, time-sensitive input) ===
{news_block}

=== YOUR TASK ===
Analyse the news items above. Select the {max_insights} most opportunity-relevant
items (favour budget/capex, executive changes, cyber, M&A, renewal, and AI/data
signals). Discard pure PR with no IBM angle.

Return a SINGLE JSON object with EXACTLY this schema (no prose outside the JSON):

{{
  "tldr": "<2-4 sentence executive summary of the whole digest: the biggest one
            or two opportunities and why they matter today>",
  "insights": [
    {{
      "headline": "<short punchy headline>",
      "account": "<JDI | IOL | GNB>",
      "trigger_type": "<capex | leadership | cyber | ma | procurement | ai_data | other>",
      "three_whys": {{
        "why_anything": "<the underlying client problem/need this signals>",
        "why_now": "<what makes it time-sensitive — the compelling event>",
        "why_ibm": "<why IBM specifically, tied to a named offering>"
      }},
      "ibm_offering": "<most relevant IBM offering(s); use the CANONICAL product name from the IBM PRODUCT TAXONOMY>",
      "product_platform": "<top-level platform/category from the taxonomy: one of 'Data/AI', 'Automation', 'Infrastructure', 'TLS', 'TEL', 'IBMz'>",
      "product_code": "<the taxonomy folder code for the named product, e.g. '02.3 IT & Asset Mgmt - Maximo_MAS'; use '' if genuinely unclear>",
      "likely_buyer": "<named buyer/champion from the grounding doc, or 'to validate'>",
      "cem_stage": "<one of: Prepare | Engage | Qualify | Design | Propose |
                     Negotiate | Closing, optionally an arrow e.g. 'Engage -> Qualify'>",
      "next_move": "<one concrete next action: a meeting, discovery question, or proof>",
      "meddpicc": {{
        "qualified": ["<MEDDPICC fields this news helps fill, e.g. 'Champion'>"],
        "open": ["<MEDDPICC fields still unqualified>"]
      }},
      "confidence": "<low | medium | high>",
      "fact_vs_inference": "<one line: what is fact from the article vs your inference>",
      "source_title": "<exact article title>",
      "source_link": "<exact article URL>"
    }}
  ]
}}

MEDDPICC fields to choose from: Metrics, Economic Buyer, Decision Criteria,
Decision Process, Paper Process, Implicate Pain, Champion, Competition.
Always map ibm_offering to the closest CANONICAL product in the IBM PRODUCT
TAXONOMY and fill product_platform + product_code accordingly (never invent a
product that isn't in the taxonomy).
Order insights most-to-least compelling. Output ONLY the JSON object.
"""


STANDING_TEMPLATE = """\
=== GROUNDING KNOWLEDGE BASE (authoritative background) ===
{grounding}

=== IBM PRODUCT TAXONOMY (map every play to a canonical product + code here) ===
{product_hierarchy}

=== YOUR TASK ===
There is NO fresh client news today. Using ONLY the grounding briefs and taxonomy
above (do not invent anything), surface the {max_plays} most compelling STANDING
opportunities the team should be actioning right now — known compelling events
already documented in the briefs, such as the Irving Oil on-premise renewal
(closes 30 June 2026), JDI's active >$1.3B capital programs, Maximo/asset plays
tied to the capex anchors, or the security/resilience entry points. Favour the
most time-sensitive and highest-value.

Return a SINGLE JSON object with this schema (no prose outside the JSON):
{{
  "tldr": "<2-3 sentences: note there is no fresh news today, then state the
            standing play(s) worth actioning now and why they're time-sensitive>",
  "insights": [
    {{
      "headline": "<short punchy standing-play headline>",
      "account": "<JDI | IOL | GNB>",
      "trigger_type": "standing",
      "three_whys": {{
        "why_anything": "<the standing client need from the brief>",
        "why_now": "<why it is time-sensitive even without news (deadline, capex window)>",
        "why_ibm": "<why IBM, tied to a named offering>"
      }},
      "ibm_offering": "<canonical product name from the IBM PRODUCT TAXONOMY>",
      "product_platform": "<Data/AI | Automation | Infrastructure | TLS | TEL | IBMz>",
      "product_code": "<taxonomy folder code, or ''>",
      "likely_buyer": "<named buyer/champion from the brief, or 'to validate'>",
      "cem_stage": "<Prepare | Engage | Qualify | Design | Propose | Negotiate | Closing>",
      "next_move": "<one concrete next action this week>",
      "meddpicc": {{"qualified": ["..."], "open": ["..."]}},
      "confidence": "<low | medium | high>",
      "fact_vs_inference": "<what is grounded in the brief vs inferred>",
      "source_title": "<cite the brief, e.g. 'IBM <account> account brief - Client_News_to_IBM_Opportunity_Insights.md SS6.6 (IBM Confidential)'>",
      "source_link": ""
    }}
  ]
}}
Every fact must be traceable to the grounding briefs above — cite the relevant
section in source_title. Do not state figures, dates, or contacts not in the briefs.
Output ONLY the JSON object.
"""


# Deterministic, no-LLM fallback so the email is NEVER empty and NEVER crashes,
# even if the model errors or returns unparseable JSON. Grounded in the briefs.
STATIC_STANDING_PLAYS = {
    "tldr": "No fresh client news today. Two standing plays are worth actioning now: "
            "the Irving Oil on-premise renewal closing 30 June 2026 (convert to multi-year "
            "+ Db2 upgrade), and JDI's $1.3B+ active capex programs (Maximo MAS + integration).",
    "insights": [
        {
            "headline": "Irving Oil on-prem renewal (closes 30 Jun 2026) — convert to multi-year + Db2 upgrade",
            "account": "IOL", "trigger_type": "standing",
            "three_whys": {
                "why_anything": "Db2 Enterprise, SPSS, and WebSphere come up for renewal (~$903K annual spend).",
                "why_now": "Hard commercial gate: the on-prem renewal closes 30 June 2026.",
                "why_ibm": "Multi-year + a Db2 upgrade removes the Extended Support penalty and reframes a "
                           "transactional renewal into a modernization + watsonx reliability conversation.",
            },
            "ibm_offering": "Db2 / WebSphere multi-year renewal + Db2 upgrade",
            "product_platform": "Data/AI",
            "product_code": "01.2.3 Data Stores & Databases - Db2",
            "likely_buyer": "Kelley Greer White (SVP IS&T); Scott Hastings (CFO)",
            "cem_stage": "Negotiate -> Closing",
            "next_move": "Engage Pellera on the Db2 upgrade scope before the 30 June renewal date.",
            "meddpicc": {"qualified": ["Metrics", "Economic Buyer", "Paper Process"],
                         "open": ["Competition", "Decision Process"]},
            "confidence": "high",
            "fact_vs_inference": "Renewal date and spend are from the account brief; timing urgency is factual.",
            "source_title": "IBM Irving Oil account brief — Client_News_to_IBM_Opportunity_Insights.md §6.3, §6.6 (IBM Confidential)",
            "source_link": "",
        },
        {
            "headline": "JDI $1.3B+ capex anchors — sequence Maximo MAS + integration before design locks",
            "account": "JDI", "trigger_type": "standing",
            "three_whys": {
                "why_anything": "Active capital programs (Tissue Macon ~$600M, Pulp & Paper ~$450M+, Cavendish ~$150M) "
                                "create asset-management and integration needs.",
                "why_now": "These programs are in flight now; engaging before the design phase locks in maximizes IBM footprint.",
                "why_ibm": "Maximo MAS drives predictive maintenance/asset lifecycle; webMethods (IWHI) connects the new systems.",
            },
            "ibm_offering": "Maximo Application Suite (MAS) + webMethods Hybrid Integration (IWHI)",
            "product_platform": "Automation",
            "product_code": "02.3 IT & Asset Mgmt - Maximo_MAS",
            "likely_buyer": "Eddie Hacala (CTO); Mark Mosher (VP Pulp & Paper)",
            "cem_stage": "Engage -> Qualify",
            "next_move": "Book a Maximo MAS discovery tied to the active capex programs.",
            "meddpicc": {"qualified": ["Implicate Pain", "Champion (likely)"],
                         "open": ["Metrics / Budget", "Economic Buyer", "Competition"]},
            "confidence": "medium",
            "fact_vs_inference": "Capex programs are facts from the brief; buyer mapping is inferred.",
            "source_title": "IBM J.D. Irving account brief — Client_News_to_IBM_Opportunity_Insights.md §5.4, §5.5 (IBM Confidential)",
            "source_link": "",
        },
    ],
}


def standing_plays(client: LLMClient, max_plays: int = 2) -> dict:
    """Standing opportunities from the briefs when there's no fresh news.

    Tries the LLM first; on any error or unparseable output, returns the
    deterministic STATIC_STANDING_PLAYS so the digest is never empty / never crashes.
    """
    try:
        prompt = STANDING_TEMPLATE.format(
            grounding=config.grounding_text(),
            product_hierarchy=config.product_hierarchy_text(),
            max_plays=max_plays,
        )
        raw = client.complete(_system_prompt(), prompt, temperature=0.3, max_tokens=2500)
        parsed = _parse_json(raw)
    except Exception as exc:  # noqa: BLE001 - LLM/network errors must not crash the run
        print(f"   ! standing_plays LLM error ({exc}); using static fallback.")
        parsed = None
    if not parsed or not parsed.get("insights"):
        print("   ! Using built-in standing plays (LLM unavailable or empty).")
        return STATIC_STANDING_PLAYS
    return parsed


def _system_prompt() -> str:
    """Base system prompt, optionally extended with the advisor writing style.

    The style governs the PROSE inside the JSON field values only; the JSON
    schema, the 'output only JSON' rule, and the grounding guardrails still win.
    """
    spec = config.advisor_text()
    if not spec.strip():
        return SYSTEM_PROMPT
    return (
        SYSTEM_PROMPT
        + "\n\n=== HOUSE WRITING STYLE (apply to the text inside every JSON field) ===\n"
        + spec
        + "\n\nSTYLE GUARDRAILS THAT OVERRIDE THE ABOVE WHEN IN CONFLICT:\n"
        "- Output ONLY the JSON object defined in the task. No text before or after it.\n"
        "- Keep the exact JSON schema and field names; do not add or remove keys.\n"
        "- Put confidence tags ([Certain]/[Likely]/[Guessing]) inline inside the text of\n"
        "  tldr, three_whys, next_move, and fact_vs_inference.\n"
        "- Lead the tldr with the single most important or most challenging point.\n"
        "- No em dashes or en dashes in any field text.\n"
    )


def _news_block(articles: list[Article]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        pub = a.published.strftime("%Y-%m-%d") if a.published else "undated"
        triggers = ", ".join(a.trigger_types) or "none"
        lines.append(
            f"[{i}] ACCOUNT={a.account} ({a.account_label}) | {pub} | "
            f"score={a.score} | triggers={triggers}\n"
            f"    TITLE: {a.title}\n"
            f"    SOURCE: {a.source}\n"
            f"    LINK: {a.link}\n"
            f"    SUMMARY: {a.summary[:600]}"
        )
    return "\n\n".join(lines)


def summarize(articles: list[Article], client: LLMClient) -> dict:
    """Return the structured digest dict (tldr + insights)."""
    if not articles:
        return {"tldr": "No relevant client news in the last 24 hours.",
                "insights": []}

    sset = config.settings()["summarization"]
    prompt = USER_TEMPLATE.format(
        grounding=config.grounding_text(),
        product_hierarchy=config.product_hierarchy_text(),
        news_block=_news_block(articles),
        max_insights=sset["max_full_insights"],
    )

    try:
        raw = client.complete(_system_prompt(), prompt, temperature=0.2, max_tokens=3500)
        parsed = _parse_json(raw)
    except Exception as exc:  # noqa: BLE001 - LLM/network errors must not crash the run
        print(f"   ! summarize LLM error ({exc}); treating as no insights.")
        parsed = None
    if parsed is None:
        print("   ! Model returned unparseable JSON; treating as no insights.")
        return {"tldr": "", "insights": []}
    return parsed


def _parse_json(raw: str) -> dict | None:
    """Best-effort extraction of the JSON object from model output.

    Returns None (never raises) if it can't be parsed, so callers can fall back
    gracefully. Tries several repairs for common LLM JSON glitches.
    """
    if not raw:
        return None
    raw = raw.strip()
    # Strip markdown code fences if present.
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]
            if raw.lstrip().lower().startswith("json"):
                raw = raw.lstrip()[4:]
    # Grab the outermost {...} span.
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]

    no_ctrl = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", raw)   # strip stray control chars
    candidates = [
        raw,
        re.sub(r",(\s*[}\]])", r"\1", raw),                       # remove trailing commas
        no_ctrl,
        re.sub(r",(\s*[}\]])", r"\1", no_ctrl),                   # both repairs
    ]
    for cand in candidates:
        try:
            data = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            data.setdefault("tldr", "")
            data.setdefault("insights", [])
            return data
    return None
