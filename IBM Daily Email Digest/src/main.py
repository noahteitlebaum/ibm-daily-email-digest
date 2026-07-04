"""IBM Daily Email Digest — orchestrator.

Pipeline:
    fetch RSS  ->  filter for relevance  ->  ICA summarize (TLDR / 3 Whys /
    CEM / MEDDPICC)  ->  build IBM-branded decks  ->  email the digest.

Usage:
    python -m src.main                 # full live run (needs .env configured)
    python -m src.main --dry-run       # no email; uses mock LLM; writes files
    python -m src.main --mock-llm      # live fetch/email but mock the LLM
    python -m src.main --no-email      # run + save outputs, skip sending
    python -m src.main --no-decks      # skip deck generation
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from datetime import datetime

from . import config, digest as digest_mod, feeds, filter as filt, state
from .llm_client import get_client
from .summarize import summarize

# Import appropriate emailer and state based on cloud provider
import os
_cloud_provider = os.getenv("CLOUD_PROVIDER", "").lower()
_email_method = os.getenv("EMAIL_METHOD", "smtp").lower()

# Import state module based on cloud provider
if _cloud_provider == "ibm":
    from . import state_cos as state
elif _email_method == "ses":
    from . import state_s3 as state
else:
    from . import state

# Import emailer based on email method
if _email_method == "sendgrid":
    from .emailer_sendgrid import send_digest
elif _email_method == "ses":
    from .emailer_ses import send_digest
else:
    from .emailer import send_digest


def _has_source(ins: dict) -> bool:
    """True only if the insight has a real, clickable http(s) source link."""
    return (ins.get("source_link") or "").strip().lower().startswith("http")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _reconcile_sources(insights: list[dict], articles: list) -> list[dict]:
    """Lock every insight to a REAL fetched article so the source link and the
    account always match a verifiable source.

    For each insight we find the backing article (by exact source link, else by
    matching the headline/source title to an article title). We then OVERWRITE
    the insight's source_link, source_title, and account from that article — so
    the source is always correct and the account always matches the source.
    Insights that can't be tied to a fetched article are dropped (no
    unverifiable claims).
    """
    by_link = {a.link: a for a in articles}
    by_title = {_norm(a.title): a for a in articles}
    out: list[dict] = []
    for ins in insights:
        link = (ins.get("source_link") or "").strip()
        art = by_link.get(link)
        if art is None:  # fall back to matching on title text
            for key in (ins.get("source_title"), ins.get("headline")):
                nk = _norm(key)
                if not nk:
                    continue
                if nk in by_title:
                    art = by_title[nk]
                    break
                # loose containment match (one title contains the other)
                for t, a in by_title.items():
                    if len(nk) > 15 and (nk in t or t in nk):
                        art = a
                        break
                if art:
                    break
        if art is None:
            continue  # cannot verify a real source for this insight -> drop it
        # Lock source + account to the verified article.
        ins["source_link"] = art.link
        ins["source_title"] = (f"{art.title} — {art.source}"
                               if art.source and art.source != "Unknown" else art.title)
        ins["account"] = art.account
        out.append(ins)
    return out


def run(dry_run: bool = False, mock_llm: bool = False,
        send: bool = True, make_decks: bool = True) -> dict:
    started = datetime.now()
    print(f"=== IBM Daily Digest run @ {started:%Y-%m-%d %H:%M} ===")

    # 1. Fetch -------------------------------------------------------------
    print("1) Fetching Google News RSS feeds...")
    articles = feeds.fetch_all()

    # 2. Filter ------------------------------------------------------------
    print("2) Scoring & filtering for relevance...")
    relevant = filt.filter_articles(articles)

    # 2b. New-since-last-run selection ------------------------------------
    client = get_client(use_mock=(dry_run or mock_llm))
    seen = state.load_seen()
    new_relevant = [a for a in relevant if a.link not in seen]
    prefer_new = config.settings().get("state", {}).get("prefer_new", True)

    # 3. Summarize — each send carries ONLY NEW opportunities from the past
    # month (relevant items not surfaced in a previous run). Already-sent items
    # are not repeated. Set state.prefer_new: false to re-send the full month.
    selection = new_relevant if prefer_new else relevant
    status_note = ""
    if selection:
        print(f"3) Summarizing {len(selection)} new opportunity article(s) via ICA/LLM...")
        digest = summarize(selection, client)
    else:
        print("   -> No new opportunities since the last run.")
        digest = {"tldr": "", "insights": []}

    # 3b. Source/account integrity: tie every insight to a REAL fetched article,
    # correcting its source link + account, and drop any we can't verify.
    before = len(digest.get("insights", []))
    reconciled = _reconcile_sources(digest.get("insights", []), articles)
    reconciled = [i for i in reconciled if _has_source(i)]
    if before - len(reconciled):
        print(f"   -> dropped {before - len(reconciled)} insight(s) without a "
              f"verifiable source/account match.")
    digest["insights"] = reconciled

    # Account radar — always included and always sourced (links resolved to
    # work). This is the guaranteed, fully-sourced daily content.
    radar = [{"title": a.title, "account": a.account_label, "link": a.link,
              "source": a.source,
              "date": a.published.strftime("%b %d") if a.published else ""}
             for a in filt.account_context(articles) if (a.link or "").startswith("http")]

    # 3c. Identify what's NEW since the last run (by source link) and remember
    # everything we surface this run — so new sources are flagged, then become
    # "seen" for next time. Covers both insight cards and the radar.
    surfaced: list[str] = []
    for ins in digest["insights"]:
        link = (ins.get("source_link") or "").strip()
        ins["is_new"] = bool(link) and link not in seen
        surfaced.append(link)
    for item in radar:
        item["is_new"] = bool(item["link"]) and item["link"] not in seen
        surfaced.append(item["link"])
    new_insights = sum(1 for i in digest["insights"] if i.get("is_new"))
    new_radar = sum(1 for r in radar if r.get("is_new"))
    state.save_seen(state.mark_seen(seen, [l for l in surfaced if l]))

    if digest["insights"]:
        n = len(digest["insights"])
        status_note = f"{n} new opportunit{'y' if n == 1 else 'ies'} from the past month."
    else:
        digest["tldr"] = digest.get("tldr") or (
            "No source-backed opportunity insights today. See the account radar "
            "below for recent sourced news on JDI, Irving Oil, and GNB.")
        status_note = (f"No opportunity insights today — {new_radar} new item(s) in the "
                       "account radar below." if new_radar else
                       "No source-backed opportunities today — see the account radar below.")
    print(f"   -> {len(digest['insights'])} sourced insight(s) ({new_insights} new); "
          f"radar: {len(radar)} item(s) ({new_radar} new).")

    # 4. Persist outputs ---------------------------------------------------
    out = config.output_dir()
    stamp = started.strftime("%Y-%m-%d")
    html_body = digest_mod.render_html(digest, len(relevant), status_note=status_note,
                                       radar=radar)
    text_body = digest_mod.render_text(digest, status_note=status_note, radar=radar)

    oset = config.settings()["output"]
    if oset.get("save_html", True):
        (out / f"digest_{stamp}.html").write_text(html_body, encoding="utf-8")
    if oset.get("save_json", True):
        record = {"generated": started.isoformat(),
                  "articles_screened": len(articles),
                  "articles_relevant": len(relevant),
                  "digest": digest,
                  "relevant_articles": [a.to_dict() for a in relevant]}
        (out / f"digest_{stamp}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8")
    print(f"   -> outputs written to {out}")

    # 5. Decks -------------------------------------------------------------
    deck_paths = []
    dset = config.settings()["decks"]
    if make_decks and dset.get("enabled", True) and digest.get("insights"):
        print("4) Generating IBM-branded opportunity decks...")
        from .deck import build_decks
        deck_paths = build_decks(
            digest["insights"],
            out / dset.get("output_subdir", "decks"),
            min_confidence=dset.get("min_confidence", "medium"),
            max_decks=dset.get("max_decks", 3),
        )
        print(f"   -> {len(deck_paths)} deck(s) created.")

    # 6. Email -------------------------------------------------------------
    only_when_new = config.settings().get("email", {}).get("only_when_new", True)
    nothing_new = (new_insights == 0 and new_radar == 0)
    if send and not dry_run and only_when_new and nothing_new:
        print("5) Email skipped — nothing new since the last run "
              "(email.only_when_new). Outputs still written.")
    elif send and not dry_run:
        print("5) Sending email...")
        n = len(digest.get("insights", []))
        subject = f"[IBM Horizon] Daily Digest — {stamp} ({n} opportunit{'y' if n == 1 else 'ies'})"
        send_digest(subject, html_body, text_body, attachments=deck_paths)
    else:
        print("5) Email skipped (dry-run/--no-email).")

    print(f"=== Done in {(datetime.now() - started).seconds}s ===")
    return digest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="IBM Daily Email Digest")
    p.add_argument("--dry-run", action="store_true",
                   help="No email; mock LLM; write files only.")
    p.add_argument("--mock-llm", action="store_true", help="Use the mock LLM.")
    p.add_argument("--no-email", action="store_true", help="Don't send email.")
    p.add_argument("--no-decks", action="store_true", help="Skip deck generation.")
    p.add_argument("--test-email", metavar="ADDR", nargs="?", const="__self__",
                   help="Send a one-line test email (to ADDR, or EMAIL_FROM/EMAIL_TO "
                        "if omitted) and exit, to confirm delivery works.")
    args = p.parse_args(argv)

    if args.test_email is not None:
        from .emailer import send_test
        addr = args.test_email
        if addr == "__self__":
            addr = (config.env("EMAIL_FROM")
                    or (config.env("EMAIL_TO") or "").split(",")[0].strip())
        if not addr:
            print("ERROR: no test address — pass one (e.g. --test-email you@x.com) "
                  "or set EMAIL_FROM/EMAIL_TO in .env.", file=sys.stderr)
            return 1
        try:
            print(f"Sending test email to {addr}...")
            send_test(addr)
            return 0
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc}", file=sys.stderr)
            traceback.print_exc()
            return 1

    try:
        run(dry_run=args.dry_run, mock_llm=args.mock_llm,
            send=not args.no_email, make_decks=not args.no_decks)
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level guard for scheduled runs
        print(f"ERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
