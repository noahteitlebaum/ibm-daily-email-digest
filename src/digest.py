"""Render the structured digest into a polished HTML email (and plain text).

Design goals: TLDR-first, scannable "at a glance" strip, and per-insight cards
where the actionable parts (the IBM play, the recommended next move, and
confidence) are visually emphasised. Built email-client-safe: inline styles and
table-based layout only (no external CSS/JS, no flexbox dependence).
"""
from __future__ import annotations

import html
import urllib.parse
from datetime import datetime

# IBM Carbon palette
IBM_BLUE = "#0F62FE"
IBM_BLUE_DK = "#0043CE"
IBM_DARK = "#161616"
IBM_GRAY = "#525252"
IBM_GRAY_LT = "#8d8d8d"
IBM_LIGHT = "#f4f4f4"
IBM_LINE = "#e0e0e0"
GREEN = "#198038"
AMBER = "#8a6d00"
RED = "#da1e28"

ACCOUNT_LABELS = {"JDI": "J.D. Irving", "IOL": "Irving Oil",
                  "GNB": "Government of New Brunswick",
                  "LCBO": "LCBO", "LOBLAWS": "Loblaw",
                  "GNL": "Gov. of Newfoundland & Labrador",
                  "GNS": "Gov. of Nova Scotia", "EMERA": "Emera",
                  "INTERAC": "Interac", "SYMCOR": "Symcor",
                  "PAYMENTS_CANADA": "Payments Canada",
                  "GFL": "GFL Environmental", "CBS": "Canadian Blood Services",
                  "GTAA": "Greater Toronto Airports Authority"}
ACCOUNT_COLORS = {"JDI": "#0F62FE", "IOL": "#007d79", "GNB": "#8a3ffc"}

# Full legal-ish company names used to build accurate LinkedIn people searches.
COMPANY_NAMES = {
    "JDI": "J.D. Irving", "IOL": "Irving Oil",
    "GNB": "Government of New Brunswick", "LCBO": "LCBO",
    "LOBLAWS": "Loblaw Companies", "GNL": "Government of Newfoundland and Labrador",
    "GNS": "Government of Nova Scotia", "EMERA": "Emera",
    "INTERAC": "Interac", "SYMCOR": "Symcor", "PAYMENTS_CANADA": "Payments Canada",
    "GFL": "GFL Environmental", "CBS": "Canadian Blood Services",
    "GTAA": "Greater Toronto Airports Authority",
}

# Trigger type -> (display label, colour)
TRIGGER_STYLE = {
    "capex":       ("Capex / Investment", "#198038"),
    "leadership":  ("Exec change",        "#8a3ffc"),
    "cyber":       ("Cybersecurity",      "#da1e28"),
    "ma":          ("M&A / Restructure",  "#007d79"),
    "procurement": ("Procurement / Renewal", "#0F62FE"),
    "ai_data":     ("AI / Data",          "#4589ff"),
    "other":       ("Signal",             "#525252"),
}
CONF_COLOR = {"high": GREEN, "medium": AMBER, "low": IBM_GRAY_LT}


def _esc(text) -> str:
    return html.escape(str(text)) if text is not None else ""


def _chip(text: str, color: str, *, filled: bool = True) -> str:
    if filled:
        return (f'<span style="display:inline-block;background:{color};color:#fff;'
                f'font-size:11px;font-weight:700;padding:3px 9px;border-radius:12px;'
                f'margin:0 6px 0 0;white-space:nowrap;">{_esc(text)}</span>')
    return (f'<span style="display:inline-block;border:1px solid {color};color:{color};'
            f'font-size:11px;font-weight:700;padding:2px 8px;border-radius:12px;'
            f'margin:0 6px 0 0;white-space:nowrap;">{_esc(text)}</span>')


def _trigger_chip(trigger: str) -> str:
    label, color = TRIGGER_STYLE.get((trigger or "other").lower(), TRIGGER_STYLE["other"])
    return _chip(label, color)


def _new_badge(is_new: bool) -> str:
    """Green 'NEW' chip for items surfaced for the first time."""
    return _chip("\U0001F195 NEW", GREEN) if is_new else ""


def _platform_tag(ins: dict) -> str:
    """Small platform pill shown next to the 'IBM Play' label."""
    platform = (ins.get("product_platform") or "").strip()
    if not platform:
        return ""
    return (f'<span style="display:inline-block;background:#d0e2ff;color:{IBM_BLUE_DK};'
            f'font-size:9px;font-weight:700;padding:1px 7px;border-radius:10px;'
            f'margin-left:8px;letter-spacing:0;">{_esc(platform)}</span>')


def _source_line(ins: dict) -> str:
    """Render the source attribution.

    - If there's a real URL (news items), render a clickable link.
    - If not (standing plays grounded in the internal briefs), render the
      source as plain text labelled 'Source' — never a dead link.
    """
    title = ins.get("source_title") or "Source"
    link = (ins.get("source_link") or "").strip()
    if link:
        return (f'<a href="{_esc(link)}" style="color:{IBM_BLUE};text-decoration:none;'
                f'font-weight:600;">&#128279; {_esc(title)}</a>')
    return (f'<span style="color:{IBM_GRAY};font-weight:600;">&#128196; Source: '
            f'{_esc(title)}</span>')


def _product_code_line(ins: dict) -> str:
    """Monospace folder-code line under the offering name."""
    code = (ins.get("product_code") or "").strip()
    if not code:
        return ""
    return (f'<div style="font-size:11px;color:{IBM_GRAY};margin-top:2px;'
            f'font-family:\'IBM Plex Mono\',Consolas,monospace;">{_esc(code)}</div>')


def _company_name(acct: str) -> str:
    key = (acct or "").upper()
    return COMPANY_NAMES.get(key) or ACCOUNT_LABELS.get(key, acct or "")


def _contact_search_query(company: str, role: str) -> str:
    """Build a LinkedIn people-search query. If the role text embeds a real name
    from the brief ('... (named in brief: Jane Doe)'), search that name; else the
    role/title. Company scopes it to the right org."""
    r = role or ""
    marker = "named in brief:"
    low = r.lower()
    if marker in low:
        term = r[low.find(marker) + len(marker):].split(")")[0].strip() or r
    else:
        term = r
    return f"{company} {term}".strip()


def _linkedin_people_url(query: str) -> str:
    return ("https://www.linkedin.com/search/results/people/?keywords="
            + urllib.parse.quote(query))


def _salesnav_url(query: str) -> str:
    """Deep-link into LinkedIn Sales Navigator people search, seeded with the
    company + name/role. Opens the filtered list inside Sales Nav in one click
    (requires the user to be signed in to Sales Navigator)."""
    return ("https://www.linkedin.com/sales/search/people?keywords="
            + urllib.parse.quote(query))


def _websearch_url(query: str) -> str:
    """One-click Google web search built from the opportunity (company + role +
    'LinkedIn'). Opens the results in the browser, where LinkedIn shows full
    names — the reliable, click-through form of 'search this on the web'."""
    return "https://www.google.com/search?q=" + urllib.parse.quote(f"{query} LinkedIn")


def _linkedin_google_url(query: str) -> str:
    """Find the person's LinkedIn profile via a Google search restricted to
    LinkedIn profiles (site:linkedin.com/in). Lands in a Google search bar with
    their profile as a top result and never hits a LinkedIn login wall."""
    return "https://www.google.com/search?q=" + urllib.parse.quote(f"site:linkedin.com/in {query}")


def _outreach_kit(ins: dict) -> str:
    """Action block shown ONLY for medium/high-confidence opportunities:
    who to contact (role + one-click LinkedIn search), when to reach out, and a
    copy-ready sample email. Never renders for low confidence or radar/news items.
    """
    conf = (ins.get("confidence") or "").lower()
    if conf not in ("medium", "high"):
        return ""
    contacts = ins.get("key_contacts") or []
    timing = (ins.get("outreach_timing") or "").strip()
    email = ins.get("sample_email") or {}
    subject = (email.get("subject") or "").strip()
    body = (email.get("body") or "").strip()
    if not contacts and not timing and not subject and not body:
        return ""

    company = _company_name(ins.get("account", ""))

    contact_rows = ""
    for c in contacts:
        role = (c.get("role") or "").strip()
        if not role:
            continue
        why = (c.get("why") or "").strip()
        query = _contact_search_query(company, role)
        snav = _salesnav_url(query)
        li = _linkedin_google_url(query)
        web = _websearch_url(query)
        sep = (f'<span style="color:{IBM_GRAY_LT};font-size:11px;">&nbsp;&middot;&nbsp;</span>')
        contact_rows += (
            f'<tr><td style="padding:5px 0;border-bottom:1px solid #eef2ff;">'
            f'<div style="font-size:13px;font-weight:600;color:{IBM_DARK};">{_esc(role)}</div>'
            f'<div style="margin-top:2px;">'
            f'<a href="{_esc(snav)}" style="color:{IBM_BLUE_DK};text-decoration:none;font-size:11px;'
            f'font-weight:700;white-space:nowrap;">&#128269; Open in Sales Navigator</a>'
            f'{sep}'
            f'<a href="{_esc(li)}" style="color:{IBM_BLUE};text-decoration:none;font-size:11px;'
            f'font-weight:600;white-space:nowrap;">LinkedIn</a>'
            f'{sep}'
            f'<a href="{_esc(web)}" style="color:{IBM_BLUE};text-decoration:none;font-size:11px;'
            f'font-weight:600;white-space:nowrap;">&#127760; Web search</a></div>'
            + (f'<div style="font-size:11px;color:{IBM_GRAY};margin-top:1px;">{_esc(why)}</div>'
               if why else "")
            + '</td></tr>'
        )
    contacts_block = (
        f'<div style="font-size:10px;font-weight:700;letter-spacing:1px;color:{IBM_GRAY};'
        f'text-transform:uppercase;margin-bottom:2px;">Who to contact</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{contact_rows}</table>'
    ) if contact_rows else ""

    timing_block = (
        f'<div style="font-size:10px;font-weight:700;letter-spacing:1px;color:{IBM_GRAY};'
        f'text-transform:uppercase;margin:10px 0 2px;">When to reach out</div>'
        f'<div style="font-size:13px;color:{IBM_DARK};">{_esc(timing)}</div>'
    ) if timing else ""

    email_block = ""
    if subject or body:
        body_html = _esc(body).replace("\n", "<br>")
        email_block = (
            f'<div style="font-size:10px;font-weight:700;letter-spacing:1px;color:{IBM_GRAY};'
            f'text-transform:uppercase;margin:10px 0 4px;">Sample email</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="background:#fff;border:1px dashed #a6c8ff;border-radius:6px;"><tr>'
            f'<td style="padding:10px 12px;">'
            + (f'<div style="font-size:12px;color:{IBM_GRAY};margin-bottom:5px;">'
               f'<b style="color:{IBM_DARK};">Subject:</b> {_esc(subject)}</div>' if subject else "")
            + (f'<div style="font-size:13px;color:{IBM_DARK};line-height:1.55;">{body_html}</div>'
               if body else "")
            + '</td></tr></table>'
            f'<div style="font-size:10px;color:{IBM_GRAY_LT};font-style:italic;margin-top:3px;">'
            f'Draft — personalize the name and verify details before sending.</div>'
        )

    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:#f7f9ff;border:1px solid #d0e2ff;border-radius:6px;margin:12px 0 4px;">'
        f'<tr><td style="padding:12px 14px;">'
        f'<div style="font-size:11px;font-weight:700;letter-spacing:1px;color:{IBM_BLUE_DK};'
        f'text-transform:uppercase;margin-bottom:6px;">&#9993;&#65039; Outreach kit</div>'
        f'{contacts_block}{timing_block}{email_block}'
        f'</td></tr></table>'
    )


def _glance_row(idx: int, ins: dict) -> str:
    acct = ins.get("account", "")
    acct_color = ACCOUNT_COLORS.get(acct, IBM_GRAY)
    conf = (ins.get("confidence") or "").lower()
    return f"""
      <tr>
        <td style="padding:7px 10px;vertical-align:top;width:26px;">
          <div style="width:22px;height:22px;background:{IBM_DARK};color:#fff;border-radius:50%;
                      text-align:center;line-height:22px;font-size:12px;font-weight:700;">{idx}</div>
        </td>
        <td style="padding:7px 10px 7px 0;vertical-align:top;">
          <span style="font-size:14px;font-weight:600;color:{IBM_DARK};">{_esc(ins.get('headline'))}</span>
          <span style="display:inline-block;font-size:11px;font-weight:700;color:{acct_color};
                       margin-left:6px;">{_esc(ACCOUNT_LABELS.get(acct, acct))}</span>
        </td>
        <td style="padding:7px 10px;vertical-align:top;text-align:right;white-space:nowrap;">
          <span style="font-size:11px;font-weight:700;color:{CONF_COLOR.get(conf, IBM_GRAY_LT)};">
            {_esc(conf.upper() or '—')}</span>
        </td>
      </tr>"""


def _insight_card(idx: int, ins: dict) -> str:
    whys = ins.get("three_whys", {})
    medd = ins.get("meddpicc", {})
    conf = (ins.get("confidence") or "").lower()
    acct = ins.get("account", "")
    acct_color = ACCOUNT_COLORS.get(acct, IBM_BLUE)
    qualified = medd.get("qualified", []) or []
    open_fields = medd.get("open", []) or []

    qual_html = "".join(
        f'<div style="font-size:12px;color:{IBM_DARK};padding:2px 0;">'
        f'<span style="color:{GREEN};font-weight:700;">&#10003;</span> {_esc(q)}</div>'
        for q in qualified) or f'<div style="font-size:12px;color:{IBM_GRAY_LT};">&mdash;</div>'
    open_html = "".join(
        f'<div style="font-size:12px;color:{IBM_DARK};padding:2px 0;">'
        f'<span style="color:{AMBER};font-weight:700;">&#9675;</span> {_esc(o)}</div>'
        for o in open_fields) or f'<div style="font-size:12px;color:{IBM_GRAY_LT};">&mdash;</div>'

    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid {IBM_LINE};border-left:5px solid {acct_color};
                  border-radius:6px;margin:0 0 18px 0;background:#fff;">
      <tr><td style="padding:18px 20px;">

        <!-- header: rank + chips + confidence -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
          <td style="vertical-align:middle;width:30px;">
            <div style="width:26px;height:26px;background:{IBM_DARK};color:#fff;border-radius:50%;
                        text-align:center;line-height:26px;font-size:13px;font-weight:700;">{idx}</div>
          </td>
          <td style="vertical-align:middle;padding-left:10px;">
            {_new_badge(ins.get('is_new'))}{_chip(ACCOUNT_LABELS.get(acct, acct), acct_color)}{_trigger_chip(ins.get('trigger_type'))}
          </td>
          <td style="vertical-align:middle;text-align:right;white-space:nowrap;">
            {_chip('Confidence: ' + (conf or 'n/a'), CONF_COLOR.get(conf, IBM_GRAY_LT), filled=False)}
          </td>
        </tr></table>

        <!-- headline -->
        <div style="font-size:18px;font-weight:700;color:{IBM_DARK};line-height:1.3;margin:12px 0 4px;">
          {_esc(ins.get('headline'))}
        </div>

        <!-- THE IBM PLAY: emphasised highlight box -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="background:{IBM_LIGHT};border-radius:6px;margin:12px 0;">
          <tr><td style="padding:12px 14px;border-left:3px solid {IBM_BLUE};">
            <div style="font-size:10px;font-weight:700;letter-spacing:1px;color:{IBM_BLUE_DK};
                        text-transform:uppercase;">IBM Play{_platform_tag(ins)}</div>
            <div style="font-size:15px;font-weight:700;color:{IBM_DARK};margin-top:3px;">
              {_esc(ins.get('ibm_offering'))}</div>
            {_product_code_line(ins)}
            <div style="font-size:12px;color:{IBM_GRAY};margin-top:5px;">
              <b>Buyer:</b> {_esc(ins.get('likely_buyer'))}
              &nbsp;&nbsp;|&nbsp;&nbsp; <b>CEM stage:</b> {_esc(ins.get('cem_stage'))}</div>
          </td></tr>
        </table>

        <!-- 3 Why's -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0;">
          <tr>
            <td style="width:96px;vertical-align:top;padding:4px 0;font-size:11px;font-weight:700;
                       color:{IBM_BLUE};text-transform:uppercase;">Why anything</td>
            <td style="vertical-align:top;padding:4px 0;font-size:13px;color:{IBM_DARK};">
              {_esc(whys.get('why_anything'))}</td>
          </tr>
          <tr>
            <td style="vertical-align:top;padding:4px 0;font-size:11px;font-weight:700;
                       color:{IBM_BLUE};text-transform:uppercase;">Why now</td>
            <td style="vertical-align:top;padding:4px 0;font-size:13px;color:{IBM_DARK};">
              {_esc(whys.get('why_now'))}</td>
          </tr>
          <tr>
            <td style="vertical-align:top;padding:4px 0;font-size:11px;font-weight:700;
                       color:{IBM_BLUE};text-transform:uppercase;">Why IBM</td>
            <td style="vertical-align:top;padding:4px 0;font-size:13px;color:{IBM_DARK};">
              {_esc(whys.get('why_ibm'))}</td>
          </tr>
        </table>

        <!-- MEDDPICC two-column -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="border-top:1px solid #efefef;margin-top:8px;">
          <tr>
            <td style="width:50%;vertical-align:top;padding:10px 12px 6px 0;">
              <div style="font-size:11px;font-weight:700;color:{GREEN};text-transform:uppercase;
                          margin-bottom:4px;">Qualified</div>{qual_html}</td>
            <td style="width:50%;vertical-align:top;padding:10px 0 6px 12px;border-left:1px solid #efefef;">
              <div style="font-size:11px;font-weight:700;color:{AMBER};text-transform:uppercase;
                          margin-bottom:4px;">Still open</div>{open_html}</td>
          </tr>
        </table>

        <!-- NEXT MOVE: call-to-action bar -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="background:{IBM_BLUE};border-radius:6px;margin:12px 0 6px;">
          <tr><td style="padding:12px 14px;">
            <div style="font-size:10px;font-weight:700;letter-spacing:1px;color:#d0e2ff;
                        text-transform:uppercase;">&#9654; Recommended next move</div>
            <div style="font-size:14px;font-weight:700;color:#fff;margin-top:3px;">
              {_esc(ins.get('next_move'))}</div>
          </td></tr>
        </table>

        <div style="font-size:11px;color:{IBM_GRAY_LT};font-style:italic;margin-top:6px;">
          {_esc(ins.get('fact_vs_inference'))}
        </div>
        <div style="font-size:12px;margin-top:6px;">
          {_source_line(ins)}
        </div>

        {_outreach_kit(ins)}

      </td></tr>
    </table>"""


def _radar_block(radar: list | None) -> str:
    """Compact 'account radar' list of headlines shown on quiet days."""
    if not radar:
        return ""
    rows = ""
    for item in radar:
        date = _esc(item.get("date", ""))
        new_tag = (f'<span style="color:{GREEN};font-weight:700;font-size:10px;'
                   f'margin-right:6px;">\U0001F195 NEW</span>') if item.get("is_new") else ""
        rows += (
            f'<tr><td style="padding:6px 0;border-bottom:1px solid #f0f0f0;">'
            f'{new_tag}<a href="{_esc(item.get("link"))}" style="color:{IBM_DARK};'
            f'text-decoration:none;font-size:13px;font-weight:600;">{_esc(item.get("title"))}</a>'
            f'<div style="font-size:11px;color:{IBM_GRAY_LT};margin-top:2px;">'
            f'{_esc(item.get("account"))}'
            f'{" &middot; " + _esc(item.get("source")) if item.get("source") else ""}'
            f'{" &middot; " + date if date else ""}</div></td></tr>'
        )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:#fff;border:1px solid {IBM_LINE};border-radius:6px;margin:18px 0 0;">'
        f'<tr><td style="padding:10px 14px;border-bottom:1px solid {IBM_LINE};">'
        f'<span style="font-size:11px;font-weight:700;letter-spacing:1px;color:{IBM_GRAY};'
        f'text-transform:uppercase;">&#128225; Account radar — in the news (past 30 days)</span></td></tr>'
        f'<tr><td style="padding:6px 16px 10px;"><table width="100%" '
        f'cellpadding="0" cellspacing="0">{rows}</table></td></tr></table>'
    )


def render_html(digest: dict, article_count: int, status_note: str = "",
                radar: list | None = None) -> str:
    today = datetime.now().strftime("%A, %B %d, %Y")
    insights = digest.get("insights", [])
    note_block = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:0 0 16px;"><tr><td style="background:#edf5ff;border-left:3px solid '
        f'{IBM_BLUE};border-radius:4px;padding:9px 13px;font-size:12px;font-weight:600;'
        f'color:{IBM_BLUE_DK};">&#9889; {_esc(status_note)}</td></tr></table>'
    ) if status_note else ""

    glance = "".join(_glance_row(i, ins) for i, ins in enumerate(insights, 1))
    glance_block = f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="background:#fff;border:1px solid {IBM_LINE};border-radius:6px;margin:0 0 20px;">
        <tr><td style="padding:6px 12px;border-bottom:1px solid {IBM_LINE};">
          <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:{IBM_GRAY};
                       text-transform:uppercase;">At a glance</span></td></tr>
        <tr><td style="padding:4px 6px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{glance}</table>
        </td></tr>
      </table>""" if insights else ""

    cards = "\n".join(_insight_card(i, ins) for i, ins in enumerate(insights, 1)) or \
        (f'<p style="color:{IBM_GRAY};font-size:14px;">No opportunity cards today — '
         f'see the account radar below for what\'s in the news.</p>' if radar else
         f'<p style="color:{IBM_GRAY};font-size:14px;">Digest is being prepared — '
         f'no items to show right now.</p>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{IBM_LIGHT};
             font-family:'IBM Plex Sans',Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{IBM_LIGHT};">
    <tr><td align="center" style="padding:24px 12px;">
      <table role="presentation" width="680" cellpadding="0" cellspacing="0" style="max-width:680px;width:100%;">

        <!-- header -->
        <tr><td style="background:{IBM_DARK};color:#fff;padding:22px 26px;border-radius:6px 6px 0 0;">
          <div style="font-size:11px;letter-spacing:2px;color:#a8a8a8;font-weight:700;">IBM HORIZON ATLANTIC</div>
          <div style="font-size:24px;font-weight:700;margin-top:2px;">Daily Client Opportunity Digest</div>
          <div style="font-size:13px;color:#c6c6c6;margin-top:4px;">{today}</div>
        </td></tr>

        <!-- TLDR -->
        <tr><td style="background:{IBM_BLUE};color:#fff;padding:18px 26px;">
          <div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#d0e2ff;">TLDR</div>
          <div style="font-size:15px;line-height:1.55;margin-top:6px;">{_esc(digest.get('tldr'))}</div>
        </td></tr>

        <!-- body -->
        <tr><td style="background:#fff;padding:22px 26px;border-radius:0 0 6px 6px;">
          <div style="font-size:12px;color:{IBM_GRAY};margin-bottom:16px;">
            <b style="color:{IBM_DARK};">{len(insights)}</b> opportunity insight(s) from
            <b style="color:{IBM_DARK};">{article_count}</b> screened article(s) &mdash;
            J.D. Irving, Irving Oil &amp; the Government of New Brunswick.
          </div>
          {note_block}
          {glance_block}
          {cards}
          {_radar_block(radar)}
        </td></tr>

        <!-- footer -->
        <tr><td style="text-align:center;color:{IBM_GRAY_LT};font-size:11px;padding:18px;line-height:1.5;">
          IBM Confidential &mdash; generated automatically.<br>
          Insights are AI-assisted; verify before client use.
        </td></tr>

      </table>
    </td></tr>
  </table>
</body></html>"""


def render_text(digest: dict, status_note: str = "", radar: list | None = None) -> str:
    lines = [f"IBM HORIZON ATLANTIC — DAILY DIGEST ({datetime.now():%Y-%m-%d})", "=" * 60, ""]
    if status_note:
        lines += [f">> {status_note}", ""]
    lines += ["TLDR:", digest.get("tldr", ""), ""]
    for i, ins in enumerate(digest.get("insights", []), 1):
        whys = ins.get("three_whys", {})
        medd = ins.get("meddpicc", {})
        lines += [
            f"[{i}]{' [NEW]' if ins.get('is_new') else ''} {ins.get('headline')}  "
            f"({ACCOUNT_LABELS.get(ins.get('account'), '')})",
            f"    Trigger: {ins.get('trigger_type')} | Confidence: {ins.get('confidence')}",
            f"    Why anything: {whys.get('why_anything')}",
            f"    Why now:      {whys.get('why_now')}",
            f"    Why IBM:      {whys.get('why_ibm')}",
            f"    IBM play: {ins.get('ibm_offering')}"
            + (f"  [{ins.get('product_platform')}]" if ins.get('product_platform') else ""),
            f"    Product:  {ins.get('product_code') or '—'}",
            f"    Buyer:    {ins.get('likely_buyer')}",
            f"    CEM stage: {ins.get('cem_stage')}",
            f"    >> Next move: {ins.get('next_move')}",
            f"    MEDDPICC qualified: {', '.join(medd.get('qualified', [])) or '—'}",
            f"    MEDDPICC open:      {', '.join(medd.get('open', [])) or '—'}",
            f"    Source: {ins.get('source_link')}",
        ]
        if (ins.get("confidence") or "").lower() in ("medium", "high"):
            company = _company_name(ins.get("account", ""))
            contacts = ins.get("key_contacts") or []
            timing = (ins.get("outreach_timing") or "").strip()
            email = ins.get("sample_email") or {}
            subject = (email.get("subject") or "").strip()
            body = (email.get("body") or "").strip()
            if contacts or timing or subject or body:
                lines.append("    --- OUTREACH KIT ---")
            for c in contacts:
                role = (c.get("role") or "").strip()
                if not role:
                    continue
                query = _contact_search_query(company, role)
                lines.append(f"    Contact: {role}")
                if c.get("why"):
                    lines.append(f"             {c.get('why')}")
                lines.append(f"             Sales Navigator: {_salesnav_url(query)}")
                lines.append(f"             LinkedIn: {_linkedin_google_url(query)}")
                lines.append(f"             Web search: {_websearch_url(query)}")
            if timing:
                lines.append(f"    When: {timing}")
            if subject:
                lines.append(f"    Email subject: {subject}")
            if body:
                lines.append(f"    Email: {body}")
        lines.append("")
    if radar:
        lines += ["", "ACCOUNT RADAR — in the news (past 30 days):"]
        for item in radar:
            tag = "[NEW] " if item.get("is_new") else ""
            lines.append(f"  - {tag}{item.get('title')} ({item.get('account')}) {item.get('link')}")
    lines += ["", "-" * 60, "IBM Confidential — AI-assisted; verify before client use."]
    return "\n".join(lines)
