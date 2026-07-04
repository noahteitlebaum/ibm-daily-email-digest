"""SendGrid email sender for IBM Cloud Functions deployment.

Uses the SendGrid API instead of SMTP for reliable cloud email delivery.
SendGrid is IBM's recommended email service and provides excellent deliverability,
detailed analytics, and integrates seamlessly with IBM Cloud.

Environment variables required:
  - SENDGRID_API_KEY: SendGrid API key (from SendGrid dashboard)
  - EMAIL_FROM: Verified sender email address in SendGrid
  - EMAIL_TO: Comma-separated recipient email addresses
  
SendGrid Setup Requirements:
  1. Create SendGrid account (free tier: 100 emails/day)
  2. Verify sender email address in SendGrid console
  3. Create API key with "Mail Send" permissions
  4. Add sender to Single Sender Verification or Domain Authentication
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _recipients() -> list[str]:
    """Parse EMAIL_TO environment variable into list of recipients."""
    raw = os.getenv("EMAIL_TO", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


def _get_sendgrid_client():
    """Get SendGrid API client."""
    try:
        from sendgrid import SendGridAPIClient
        api_key = os.getenv("SENDGRID_API_KEY")
        if not api_key:
            raise RuntimeError(
                "SENDGRID_API_KEY not configured. Set this environment variable to your "
                "SendGrid API key from https://app.sendgrid.com/settings/api_keys"
            )
        return SendGridAPIClient(api_key)
    except ImportError as exc:
        raise RuntimeError(
            "sendgrid is required for SendGrid email delivery. "
            "Install with: pip install sendgrid"
        ) from exc


def send_digest(subject: str, html_body: str, text_body: str,
                attachments: list[Path] | None = None,
                recipients: list[str] | None = None) -> None:
    """Send digest email via SendGrid.
    
    Args:
        subject: Email subject line
        html_body: HTML version of email body
        text_body: Plain text version of email body
        attachments: Optional list of file paths to attach
        recipients: Optional list of recipient emails (overrides EMAIL_TO)
    """
    from sendgrid.helpers.mail import (
        Mail, Email, To, Content, Attachment, FileContent, 
        FileName, FileType, Disposition
    )
    import base64
    
    recipients = recipients or _recipients()
    sender = os.getenv("EMAIL_FROM")

    # Validate required configuration
    if not sender:
        raise RuntimeError(
            "EMAIL_FROM not configured. Set this environment variable to a "
            "verified SendGrid sender address."
        )
    if not recipients:
        raise RuntimeError(
            "EMAIL_TO not configured. Set this environment variable to "
            "comma-separated recipient email addresses."
        )

    # Build SendGrid message
    message = Mail(
        from_email=Email(sender, "IBM Horizon Atlantic Digest"),
        to_emails=[To(email) for email in recipients],
        subject=subject,
        plain_text_content=Content("text/plain", text_body),
        html_content=Content("text/html", html_body)
    )

    # Add attachments
    attachment_count = 0
    for path in attachments or []:
        path = Path(path)
        if not path.exists():
            logger.warning(f"Attachment not found: {path}")
            continue
        
        try:
            with open(path, 'rb') as f:
                data = f.read()
            
            encoded = base64.b64encode(data).decode()
            
            attached_file = Attachment(
                FileContent(encoded),
                FileName(path.name),
                FileType('application/vnd.openxmlformats-officedocument.presentationml.presentation'),
                Disposition('attachment')
            )
            message.add_attachment(attached_file)
            attachment_count += 1
        except Exception as exc:
            logger.error(f"Failed to attach {path}: {exc}")

    # Send via SendGrid
    try:
        sg = _get_sendgrid_client()
        response = sg.send(message)
        
        # SendGrid returns 202 for successful acceptance
        if response.status_code in (200, 202):
            logger.info(
                f"Email sent successfully via SendGrid to {', '.join(recipients)} "
                f"(Status: {response.status_code})"
                f"{f' with {attachment_count} attachment(s)' if attachment_count else ''}"
            )
        else:
            raise RuntimeError(
                f"SendGrid returned unexpected status: {response.status_code}. "
                f"Body: {response.body}"
            )
        
    except Exception as exc:
        error_msg = str(exc)
        
        # Provide helpful error messages for common SendGrid issues
        if "403" in error_msg or "Forbidden" in error_msg:
            raise RuntimeError(
                "SendGrid API key lacks permissions or sender not verified. "
                "Ensure your API key has 'Mail Send' permissions and sender email "
                "is verified in SendGrid console. "
                f"Error: {exc}"
            ) from exc
        elif "401" in error_msg or "Unauthorized" in error_msg:
            raise RuntimeError(
                "Invalid SendGrid API key. Check SENDGRID_API_KEY environment variable. "
                f"Error: {exc}"
            ) from exc
        elif "400" in error_msg or "Bad Request" in error_msg:
            raise RuntimeError(
                "Invalid email format or content. Check sender/recipient addresses. "
                f"Error: {exc}"
            ) from exc
        else:
            raise RuntimeError(f"Failed to send email via SendGrid: {exc}") from exc


def send_test(to_addr: str) -> None:
    """Send a test email to verify SendGrid configuration.
    
    Args:
        to_addr: Email address to send test to
    """
    when = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    sender = os.getenv("EMAIL_FROM") or "unknown"
    
    subject = "IBM Daily Digest — SendGrid Test Email"
    html = (
        '<div style="font-family:Helvetica,Arial,sans-serif;font-size:14px;color:#161616;">'
        '<p style="font-size:16px;font-weight:700;color:#0F62FE;">&#9989; SendGrid deployment test successful</p>'
        '<p>If you can read this, the IBM Daily Digest can deliver mail from IBM Cloud Functions via SendGrid.</p>'
        f'<p style="font-size:12px;color:#525252;">Method: <b>SendGrid</b><br>'
        f'From: <b>{sender}</b><br>Sent: {when}</p></div>'
    )
    text = (
        f"SendGrid deployment test successful. "
        f"Method: SendGrid. From: {sender}. Sent: {when}."
    )
    
    send_digest(subject, html, text, attachments=None, recipients=[to_addr])
    logger.info(f"Test email sent to {to_addr} via SendGrid")
