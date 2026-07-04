"""Cloud-compatible email sender (SMTP only, no Outlook COM).

This is a simplified version of emailer.py designed for AWS Lambda deployment.
It only supports SMTP delivery since Outlook COM requires Windows desktop.

Environment variables required:
  - SMTP_HOST: SMTP server hostname (e.g., smtp.office365.com for IBM)
  - SMTP_PORT: SMTP port (typically 587 for TLS)
  - SMTP_USERNAME: SMTP username (usually your email address)
  - SMTP_PASSWORD: SMTP password or app-specific password
  - EMAIL_FROM: Sender email address
  - EMAIL_TO: Comma-separated recipient email addresses
"""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

logger = logging.getLogger(__name__)


def _recipients() -> list[str]:
    """Parse EMAIL_TO environment variable into list of recipients."""
    raw = os.getenv("EMAIL_TO", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


def send_digest(subject: str, html_body: str, text_body: str,
                attachments: list[Path] | None = None,
                recipients: list[str] | None = None) -> None:
    """Send digest email via SMTP.
    
    Args:
        subject: Email subject line
        html_body: HTML version of email body
        text_body: Plain text version of email body
        attachments: Optional list of file paths to attach
        recipients: Optional list of recipient emails (overrides EMAIL_TO)
    """
    recipients = recipients or _recipients()
    
    # Validate required environment variables
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("EMAIL_FROM") or username

    missing = []
    if not host:
        missing.append("SMTP_HOST")
    if not username:
        missing.append("SMTP_USERNAME")
    if not password:
        missing.append("SMTP_PASSWORD")
    if not recipients:
        missing.append("EMAIL_TO")
    
    if missing:
        raise RuntimeError(
            f"Email not configured — missing environment variables: {', '.join(missing)}. "
            "Set these in Lambda environment variables or AWS Secrets Manager."
        )

    # Build email message
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = formataddr(("IBM Horizon Atlantic Digest", sender))
    msg["To"] = ", ".join(recipients)

    # Add HTML and text alternatives
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    # Add attachments
    attachment_count = 0
    for path in attachments or []:
        path = Path(path)
        if not path.exists():
            logger.warning(f"Attachment not found: {path}")
            continue
        
        try:
            part = MIMEApplication(
                path.read_bytes(),
                _subtype="vnd.openxmlformats-officedocument.presentationml.presentation"
            )
            part.add_header("Content-Disposition", "attachment", filename=path.name)
            msg.attach(part)
            attachment_count += 1
        except Exception as exc:
            logger.error(f"Failed to attach {path}: {exc}")

    # Send via SMTP
    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            server.sendmail(sender, recipients, msg.as_string())
        
        logger.info(
            f"Email sent successfully to {', '.join(recipients)}"
            f"{f' with {attachment_count} attachment(s)' if attachment_count else ''}"
        )
        
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            f"SMTP authentication failed. Check SMTP_USERNAME and SMTP_PASSWORD. "
            f"For IBM accounts, you may need an app-specific password. Error: {exc}"
        ) from exc
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"SMTP error: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to send email: {exc}") from exc


def send_test(to_addr: str) -> None:
    """Send a test email to verify SMTP configuration.
    
    Args:
        to_addr: Email address to send test to
    """
    when = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    sender = os.getenv("EMAIL_FROM") or os.getenv("SMTP_USERNAME") or "unknown"
    
    subject = "IBM Daily Digest — Cloud Test Email"
    html = (
        '<div style="font-family:Helvetica,Arial,sans-serif;font-size:14px;color:#161616;">'
        '<p style="font-size:16px;font-weight:700;color:#0F62FE;">&#9989; Cloud deployment test successful</p>'
        '<p>If you can read this, the IBM Daily Digest can deliver mail from AWS Lambda.</p>'
        f'<p style="font-size:12px;color:#525252;">Method: <b>SMTP (Cloud)</b><br>'
        f'From: <b>{sender}</b><br>Sent: {when}</p></div>'
    )
    text = (
        f"Cloud deployment test successful. "
        f"Method: SMTP (Cloud). From: {sender}. Sent: {when}."
    )
    
    send_digest(subject, html, text, attachments=None, recipients=[to_addr])
    logger.info(f"Test email sent to {to_addr}")
