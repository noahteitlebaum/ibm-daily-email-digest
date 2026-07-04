"""Send the digest — two delivery methods, chosen in config (email.method):

  * "outlook"  -> drives your installed, signed-in Outlook desktop app via COM.
                  The email is sent from your real @ibm.com account, so it passes
                  corporate authentication (SPF/DMARC) and can go to your team.
                  No app password, no IT ticket. Requires: Windows, Outlook
                  desktop installed & configured, and you logged in when it runs.

  * "sendgrid" -> SendGrid HTTPS API. Headless and cloud-friendly (IBM Code
                  Engine, etc.). Needs SENDGRID_API_KEY + a verified EMAIL_FROM.
                  This is the method used for the IBM Cloud deployment.

  * "smtp"     -> classic SMTP (Gmail/Outlook). Good for personal accounts; most
                  corporate @ibm.com mailboxes block this.

Recipients come from EMAIL_TO in .env (comma-separated).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import config


def _recipients() -> list[str]:
    raw = config.env("EMAIL_TO") or ""
    return [r.strip() for r in raw.split(",") if r.strip()]


def _method() -> str:
    # .env EMAIL_METHOD overrides settings.yaml email.method; default "smtp".
    env_m = (config.env("EMAIL_METHOD") or "").strip().lower()
    if env_m:
        return env_m
    return config.settings().get("email", {}).get("method", "smtp").lower()


def send_digest(subject: str, html_body: str, text_body: str,
                attachments: list[Path] | None = None,
                recipients: list[str] | None = None) -> None:
    method = _method()
    recipients = recipients or _recipients()
    if method == "outlook":
        _send_via_outlook(subject, html_body, attachments, recipients)
    elif method == "sendgrid":
        _send_via_sendgrid(subject, html_body, attachments, recipients)
    else:
        _send_via_smtp(subject, html_body, text_body, attachments, recipients)


def send_test(to_addr: str) -> None:
    """Send a tiny test email to confirm delivery works end-to-end."""
    method = _method()
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    sender = config.env("EMAIL_FROM") or "(Outlook default account)"
    subject = "IBM Daily Digest — test email"
    html = (
        "<div style=\"font-family:Helvetica,Arial,sans-serif;font-size:14px;color:#161616;\">"
        "<p style=\"font-size:16px;font-weight:700;color:#0F62FE;\">&#9989; Test email working</p>"
        f"<p>If you can read this, the IBM Daily Digest can deliver mail.</p>"
        f"<p style=\"font-size:12px;color:#525252;\">Method: <b>{method}</b><br>"
        f"From: <b>{sender}</b><br>Sent: {when}</p></div>"
    )
    text = f"Test email working. Method: {method}. From: {sender}. Sent: {when}."
    send_digest(subject, html, text, attachments=None, recipients=[to_addr])
    print(f"  -> test email sent to {to_addr} via {method}.")


# ---------------------------------------------------------------- Outlook (COM)
def _send_via_outlook(subject: str, html_body: str,
                      attachments: list[Path] | None, recipients: list[str]) -> None:
    """Send through the local Outlook desktop app (sends from your IBM account)."""
    try:
        import win32com.client as win32  # from pywin32 (Windows only)
    except ImportError as exc:
        raise RuntimeError(
            "Outlook send needs the 'pywin32' package. Install it with "
            "`pip install pywin32` (Windows only)."
        ) from exc

    if not recipients:
        raise RuntimeError("No recipients — set EMAIL_TO in .env.")

    try:
        outlook = win32.Dispatch("Outlook.Application")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Could not start Outlook. Make sure the Outlook desktop app is "
            "installed, configured with your IBM account, and that you are "
            "logged in to Windows when this runs."
        ) from exc

    mail = outlook.CreateItem(0)  # 0 = olMailItem
    mail.To = "; ".join(recipients)
    mail.Subject = subject
    mail.HTMLBody = html_body

    # Optionally send from a specific account instead of the default one.
    sender = config.env("EMAIL_FROM")
    if sender:
        try:
            for acct in outlook.Session.Accounts:
                if str(acct.SmtpAddress).lower() == sender.lower():
                    mail.SendUsingAccount = acct
                    break
        except Exception:  # noqa: BLE001 - non-fatal; falls back to default account
            pass

    for path in attachments or []:
        path = Path(path)
        if path.exists():
            mail.Attachments.Add(str(path.resolve()))

    mail.Send()
    print(f"  -> Outlook sent the digest to {', '.join(recipients)}"
          f"{f' with {len(attachments)} attachment(s)' if attachments else ''}")


# ------------------------------------------------------------- SendGrid (API)
def _send_via_sendgrid(subject: str, html_body: str,
                       attachments: list[Path] | None, recipients: list[str]) -> None:
    """Send via the SendGrid HTTPS API. Headless, cloud-friendly (IBM Code Engine,
    AWS, anywhere). Needs SENDGRID_API_KEY and a verified EMAIL_FROM sender.
    """
    import base64

    api_key = config.env("SENDGRID_API_KEY")
    sender = config.env("EMAIL_FROM")
    missing = [k for k, v in {"SENDGRID_API_KEY": api_key, "EMAIL_FROM": sender,
                              "EMAIL_TO": recipients}.items() if not v]
    if missing:
        raise RuntimeError(f"SendGrid not configured — missing {', '.join(missing)}.")

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (Mail, Attachment, FileContent,
                                           FileName, FileType, Disposition)
    except ImportError as exc:
        raise RuntimeError("SendGrid send needs the 'sendgrid' package "
                           "(pip install sendgrid).") from exc

    message = Mail(from_email=sender, to_emails=recipients,
                   subject=subject, html_content=html_body)
    for path in attachments or []:
        path = Path(path)
        if not path.exists():
            continue
        encoded = base64.b64encode(path.read_bytes()).decode()
        message.add_attachment(Attachment(
            FileContent(encoded), FileName(path.name),
            FileType("application/vnd.openxmlformats-officedocument."
                     "presentationml.presentation"),
            Disposition("attachment")))

    resp = SendGridAPIClient(api_key).send(message)
    print(f"  -> SendGrid sent the digest to {', '.join(recipients)} "
          f"(status {resp.status_code})")


# ----------------------------------------------------------------------- SMTP
def _send_via_smtp(subject: str, html_body: str, text_body: str,
                   attachments: list[Path] | None, recipients: list[str]) -> None:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formataddr

    host = config.env("SMTP_HOST")
    port = int(config.env("SMTP_PORT") or 587)
    username = config.env("SMTP_USERNAME")
    password = config.env("SMTP_PASSWORD")
    sender = config.env("EMAIL_FROM") or username

    missing = [k for k, v in {
        "SMTP_HOST": host, "SMTP_USERNAME": username,
        "SMTP_PASSWORD": password, "EMAIL_TO": recipients,
    }.items() if not v]
    if missing:
        raise RuntimeError(
            f"Email not configured — missing {', '.join(missing)} in .env "
            "(see .env.example)."
        )

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = formataddr(("IBM Horizon Atlantic Digest", sender))
    msg["To"] = ", ".join(recipients)

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    for path in attachments or []:
        path = Path(path)
        if not path.exists():
            continue
        from email.mime.application import MIMEApplication
        part = MIMEApplication(path.read_bytes(),
                               _subtype="vnd.openxmlformats-officedocument."
                                        "presentationml.presentation")
        part.add_header("Content-Disposition", "attachment", filename=path.name)
        msg.attach(part)

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.login(username, password)
        server.sendmail(sender, recipients, msg.as_string())

    print(f"  -> SMTP sent the digest to {', '.join(recipients)}"
          f"{f' with {len(attachments)} attachment(s)' if attachments else ''}")
