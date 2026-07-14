"""IBM Daily Email Digest — orchestrator (multi-team).

Pipeline per run:
    fetch RSS (all accounts)  ->  filter for relevance  ->  for each TEAM:
    subset to that team's accounts  ->  ICA summarize (grounded per account)
    ->  render  ->  SendGrid email to that team's recipients.

Teams are defined in config/teams.yaml (recipients + account keys). Each account
in config/keywords.yaml may declare its own grounding_file; a team's digest is
grounded with the union of its accounts' briefs.

Usage:
    python -m src.main                 # full live run (needs secrets/.env)
    python -m src.main --dry-run       # no email; mock LLM; writes files
    python -m src.main --mock-llm      # live fetch/email but mock the LLM
    python -m src.main --no-email      # run + save outputs, skip sending
    python -m src.main --test-email X  # send a one-line delivery test and exit
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from datetime import datetime

from . import config, digest as digest_mod, feeds, filter as filt, state
from .emailer_sendgrid import send_digest
from .llm_client import get_client
from .summarize import summarize


def _has_source(ins: dict) -> bool:
    """True only if the insight has a real, clickable http(s) source link."""
    return (ins.get("source_link") or "").strip().lower().startswith("http")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _reconcile_sources(insights: list[dict], articles: list) -> list[dict]:
    """Lock every insight to a REAL fetched article so the source link and the
    account always match a verifiable source. Insights that cannot be tied to a
    fetched article are dropped (no unverifiable claims).
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
                for t, a in by_title.items():
                    if len(nk) > 15 and (nk in t or t in nk):
                        art = a
                        break
                if art:
                    break
        if art is None:
            continue
        ins["source_link"] = art.link
        ins["source_title"] = (f"{art.title} — {art.source}"
                               if art.source and art.source != "Unknown" else art.title)
        ins["account"] = art.account
        out.append(ins)
    return out


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "team").lower()).strip("-")[:40] or "team"


def _default_teams() -> list[dict]:
    """Fallback when teams.yaml is absent: one team, all accounts, EMAIL_TO."""
    return [{"name": "Daily Digest",
             "recipients": [],  # send_digest falls back to EMAIL_TO
             "accounts": list(config.keywords().get("accounts", {}).keys())}]


def _process_team(team: dict, articles: list, relevant: list, client, seen: dict,
                  prefer_new: bool) -> dict:
    """Build one team's digest. Returns a dict with html, text, subject,
    recipients, new_insights, new_radar, and the surfaced links."""
    accts = set(team.get("accounts", []))
    t_articles = [a for a in articles if a.account in accts]
    t_relevant = [a for a in relevant if a.account in accts]
    new_relevant = [a for a in t_relevant if a.link not in seen]
    selection = new_relevant if prefer_new else t_relevant

    grounding = config.grounding_for(team.get("accounts", []))
    if selection:
        print(f"   [{team['name']}] summarizing {len(selection)} article(s)"
              f" ({'grounded' if grounding else 'news-only'})...")
        digest = summarize(selection, client, grounding=grounding)
    else:
        digest = {"tldr": "", "insights": []}

    # Source/account integrity.
    digest["insights"] = [i for i in _reconcile_sources(digest.get("insights", []), t_articles)
                          if _has_source(i)]

    # Account radar — always sourced, working links.
    radar = [{"title": a.title, "account": a.account_label, "link": a.link,
              "source": a.source,
              "date": a.published.strftime("%b %d") if a.published else ""}
             for a in filt.account_context(t_articles) if (a.link or "").startswith("http")]

    # NEW-since-last-run flags.
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

    if digest["insights"]:
        n = len(digest["insights"])
        status_note = f"{n} new opportunit{'y' if n == 1 else 'ies'} from the past month."
    else:
        digest["tldr"] = digest.get("tldr") or (
            "No source-backed opportunity insights today. See the account radar "
            "below for recent sourced news.")
        status_note = (f"No opportunity insights today — {new_radar} new item(s) in the "
                       "account radar below." if new_radar else
                       "No source-backed opportunities today — see the account radar below.")

    html_body = digest_mod.render_html(digest, len(t_relevant), status_note=status_note, radar=radar)
    text_body = digest_mod.render_text(digest, status_note=status_note, radar=radar)
    n = len(digest["insights"])
    subject = (f"[IBM] {team['name']} — Daily Digest "
               f"({n} opportunit{'y' if n == 1 else 'ies'})")
    return {"html": html_body, "text": text_body, "subject": subject,
            "recipients": team.get("recipients") or None, "digest": digest,
            "radar": radar, "new_insights": new_insights, "new_radar": new_radar,
            "surfaced": surfaced}


def run(dry_run: bool = False, mock_llm: bool = False,
        send: bool = True, make_decks: bool = True,
        only_me: bool = False, only_to: str | None = None) -> list[dict]:
    started = datetime.now()
    print(f"=== IBM Daily Digest run @ {started:%Y-%m-%d %H:%M} ===")

    # 1. Fetch (all accounts across all teams) -----------------------------
    print("1) Fetching Google News RSS feeds...")
    articles = feeds.fetch_all()

    # 2. Filter for relevance ---------------------------------------------
    print("2) Scoring & filtering for relevance...")
    relevant = filt.filter_articles(articles)

    client = get_client(use_mock=(dry_run or mock_llm))
    seen = state.load_seen()
    prefer_new = config.settings().get("state", {}).get("prefer_new", True)
    only_when_new = config.settings().get("email", {}).get("only_when_new", True)
    oset = config.settings()["output"]

    teams = config.teams() or _default_teams()
    out = config.output_dir()
    stamp = started.strftime("%Y-%m-%d")
    # Recipient override for testing: --only-to <addr> wins, else --only-me
    # (EMAIL_FROM/EMAIL_TO). When set, every team's digest goes only there.
    # Recipient policy:
    #   - You (EMAIL_FROM) ALWAYS receive every team's digest.
    #   - ONLY_TO is an allowlist of EXTERNAL recipients: a person gets a team's
    #     digest only if they are in ONLY_TO AND configured for that team, so
    #     they receive just the one(s) matching their accounts.
    #   - ONLY_TO unset (and no --only-me) => production: each team's full
    #     recipient list from teams.yaml.
    #   - --only-me => only you, every team.
    me = (config.env("EMAIL_FROM") or "").strip()
    if only_me:
        allow, gating = set(), True
    elif (only_to or "").strip():
        allow = {x.strip().lower() for x in only_to.split(",") if x.strip()}
        gating = True
    else:
        allow, gating = None, False

    # 3. One digest per team ----------------------------------------------
    print(f"3) Building {len(teams)} team digest(s)...")
    surfaced_all: list[str] = []
    results: list[dict] = []
    for team in teams:
        r = _process_team(team, articles, relevant, client, seen, prefer_new)
        surfaced_all += r["surfaced"]

        # Persist per-team outputs.
        slug = _slug(team["name"])
        if oset.get("save_html", True):
            (out / f"digest_{stamp}_{slug}.html").write_text(r["html"], encoding="utf-8")
        if oset.get("save_json", True):
            (out / f"digest_{stamp}_{slug}.json").write_text(
                json.dumps(r["digest"], indent=2), encoding="utf-8")

        # Decide recipients per the policy above.
        if gating:
            to = [me] if me else []
            for a in r["recipients"]:
                if allow and a.strip().lower() in allow:
                    to.append(a)
            _seen: set = set()
            to = [x for x in to if x and not (x.lower() in _seen or _seen.add(x.lower()))]
        else:
            to = r["recipients"]
        nothing_new = (r["new_insights"] == 0 and r["new_radar"] == 0)
        if send and not dry_run and only_when_new and nothing_new and not gating:
            print(f"   [{team['name']}] skipped — nothing new.")
        elif send and not dry_run and to:
            send_digest(r["subject"], r["html"], r["text"], recipients=to)
            print(f"   [{team['name']}] sent to {', '.join(to)}.")
        else:
            print(f"   [{team['name']}] email skipped (dry-run / no recipients).")
        results.append(r)

    # Remember everything surfaced this run (one shot at being 'new').
    state.save_seen(state.mark_seen(seen, [l for l in surfaced_all if l]))
    print(f"=== Done in {(datetime.now() - started).seconds}s ===")
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="IBM Daily Email Digest")
    p.add_argument("--dry-run", action="store_true",
                   help="No email; mock LLM; write files only.")
    p.add_argument("--mock-llm", action="store_true", help="Use the mock LLM.")
    p.add_argument("--no-email", action="store_true", help="Don't send email.")
    p.add_argument("--no-decks", action="store_true", help="Skip deck generation.")
    p.add_argument("--only-me", action="store_true",
                   help="Send every team's digest only to yourself "
                        "(EMAIL_FROM/EMAIL_TO), ignoring team recipients. For testing.")
    p.add_argument("--only-to", metavar="ADDR", default=None,
                   help="Send every team's digest only to ADDR, ignoring team "
                        "recipients. For a single-recipient pilot.")
    p.add_argument("--test-email", metavar="ADDR", nargs="?", const="__self__",
                   help="Send a one-line test email (to ADDR, or EMAIL_FROM/EMAIL_TO "
                        "if omitted) and exit, to confirm delivery works.")
    args = p.parse_args(argv)

    if args.test_email is not None:
        from .emailer_sendgrid import send_test
        addr = args.test_email
        if addr == "__self__":
            addr = (config.env("EMAIL_FROM")
                    or (config.env("ONLY_TO") or "").split(",")[0].strip())
        if not addr:
            print("ERROR: no test address — pass one (e.g. --test-email you@x.com) "
                  "or set EMAIL_FROM/ONLY_TO in .env.", file=sys.stderr)
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
            send=not args.no_email, make_decks=not args.no_decks,
            only_me=args.only_me,
            only_to=args.only_to or config.env("ONLY_TO"))
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level guard for scheduled runs
        print(f"ERROR: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
