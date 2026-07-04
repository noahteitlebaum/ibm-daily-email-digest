# IBM Daily Email Digest — Horizon Atlantic

An automated daily intelligence digest for the IBM Horizon Atlantic account team.
It scrapes the last ~24 hours of news about **J.D. Irving**, **Irving Oil**, and the
**Government of New Brunswick**, keeps only items that signal a real IBM
opportunity (capex, executive changes, cyber incidents, M&A, renewals, AI/data
initiatives), and emails a concise, TLDR-first digest every morning.

Each opportunity is framed exactly the way the account team works:

- **The 3 Why's** — Why anything? / Why now? / Why IBM?
- **CEM stage** — where the event sits in IBM's Client Engagement Model
- **MEDDPICC** — what the news qualifies vs. what's still open

For the strongest opportunities it also auto-generates **IBM-branded PowerPoint
decks** and attaches them to the email.

---

## How it works

```
Google News RSS  ─►  relevance filter  ─►  ICA summarization  ─►  digest + decks  ─►  email
   (feeds.py)         (filter.py)          (summarize.py +         (digest.py,        (emailer.py)
                                            llm_client.py)          deck.py)
```

All reasoning is grounded in `grounding/Client_News_to_IBM_Opportunity_Insights.md`
(account briefs, IBM offerings, buyers, CEM, guardrails) — the LLM is told to use
only that knowledge base plus the news, and to separate fact from inference.

## Project layout

```
config/keywords.yaml     Accounts, entity names, people, tech signals, cautions
config/settings.yaml     Recency window, scoring weights, trigger events, deck options
grounding/               The opportunity-insight knowledge base (LLM context)
src/feeds.py             Build + fetch Google News RSS, recency-filter
src/filter.py            Score relevance + apply guardrails
src/llm_client.py        Pluggable ICA / OpenAI-compatible LLM client
src/summarize.py         Prompt the LLM -> structured digest JSON
src/digest.py            Render HTML + plain-text email
src/deck.py              Generate IBM-branded opportunity decks (.pptx)
src/emailer.py           Send via SendGrid (cloud) / SMTP / Outlook
src/main.py              Orchestrator + CLI
scripts/run_digest.bat   Daily runner (logs to output/logs)
scripts/setup_task_scheduler.ps1   Register the daily Windows task
```

## Setup (one time)

1. **Install Python 3.10+** and create a virtual environment:

   ```powershell
   cd "IBM Daily Email Digest"
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure secrets.** Copy `.env.example` to `.env` and fill it in:

   - **Email (Gmail):** set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
     your address, and a **Gmail App Password** (Google Account → Security →
     2-Step Verification → App passwords — *not* your normal password).
     For Outlook/Office365 use `smtp.office365.com`.
   - **ICA / LLM:** set `ICA_API_KEY`, `ICA_BASE_URL`, `ICA_MODEL`. The client
     defaults to the OpenAI-compatible `/chat/completions` shape (see below).

3. **Test without sending anything:**

   ```powershell
   python -m src.main --dry-run
   ```

   This uses a built-in **mock LLM** (no API key needed), fetches real feeds,
   and writes `output/digest_<date>.html`, the JSON record, and sample decks so
   you can eyeball the format.

4. **Live test (real LLM, still no email):**

   ```powershell
   python -m src.main --no-email
   ```

5. **Go live:** `python -m src.main`

## Schedule it daily

### Option 1: Local Windows (Task Scheduler)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_task_scheduler.ps1 -Time 07:00
```

Runs every day at the time you pass, even if the app/VS Code is closed (it's a
Windows Scheduled Task). Logs land in `output/logs/`. Remove it with:

```powershell
Unregister-ScheduledTask -TaskName "IBM Daily Email Digest" -Confirm:$false
```

### Option 2: IBM Code Engine (Cloud Deployment)

Deploy to IBM Code Engine for 24/7 automated execution without needing your computer on:

```bash
# Prerequisites: IBM Cloud CLI with Code Engine plugin, Docker
python deploy_code_engine.py
```

The deployment script builds/pushes the container, creates the Code Engine
project + daily scheduled job, and configures the SendGrid + ICA environment.

**See `IBM_CLOUD_DEPLOYMENT.md` for the complete, authoritative guide** — daily
schedule, SendGrid setup, secrets, known limitations, and file cleanup.

**Cost:** a few dollars/month at most, dominated by ICA/Claude tokens; Code
Engine and SendGrid free tiers cover the rest.

## Connecting the real ICA API

We default to an **OpenAI-compatible** client because that's what most IBM API
gateways expose. To point at ICA:

1. Fill in `ICA_API_KEY`, `ICA_BASE_URL` (e.g. `.../v1`), `ICA_MODEL`, and
   `ICA_AUTH_SCHEME` (`Bearer` / `ZenApiKey` / `apikey`) in `.env`.
2. If ICA's request/response JSON differs from OpenAI's, edit **only** the three
   spots marked `# >>> ICA WIRE FORMAT` in `src/llm_client.py`. Nothing else in
   the codebase needs to change.

## Tuning

- **Keywords / accounts:** `config/keywords.yaml`
- **What counts as relevant:** `config/settings.yaml` → `filtering` (weights,
  `min_relevance_score`, `trigger_events`)
- **Recency window:** `config/settings.yaml` → `feeds.max_age_hours`
- **Decks:** `config/settings.yaml` → `decks` (min confidence, max per run)

## Notes & guardrails

- Insights are **AI-assisted** — verify before any client use. Source briefs are
  IBM Confidential.
- Built-in guardrails: never pitch net-new QRadar/SIEM (IBM exited SIEM);
  complement (don't displace) Aera at JDI; don't conflict with Kent's MS D365;
  treat GNB contacts as "to validate".
- `.env` and `output/` are git-ignored.
