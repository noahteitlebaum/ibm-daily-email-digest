"""Amazon SES email sender for AWS Lambda deployment.

Uses the AWS SES API (boto3) instead of SMTP for reliable cloud email delivery.
SES provides better deliverability, no SMTP authentication issues, and integrates
natively with AWS Lambda.

Environment variables required:
  - AWS_REGION: AWS region where SES is configured (e.g., us-east-1)
  - EMAIL_FROM: Verified sender email address in SES
  - EMAIL_TO: Comma-separated recipient email addresses
  
SES Setup Requirements:
  1. Verify sender email address in SES console
  2. If in SES Sandbox, verify recipient addresses too
  3. Request production access for unrestricted sending
  4. Lambda IAM role needs ses:SendEmail and ses:SendRawEmail permissions
"""
from __future__ import annotations

import logging
import os
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


def _get_ses_client():
    """Get boto3 SES client."""
    try:
        import boto3
        region = os.getenv("AWS_REGION", "us-east-1")
        return boto3.client("ses", region_name=region)
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for SES email delivery. Install with: pip install boto3"
        ) from exc


def send_digest(subject: str, html_body: str, text_body: str,
                attachments: list[Path] | None = None,
                recipients: list[str] | None = None) -> None:
    """Send digest email via Amazon SES.
    
    Args:
        subject: Email subject line
        html_body: HTML version of email body
        text_body: Plain text version of email body
        attachments: Optional list of file paths to attach
        recipients: Optional list of recipient emails (overrides EMAIL_TO)
    """
    recipients = recipients or _recipients()
    sender = os.getenv("EMAIL_FROM")

    # Validate required configuration
    if not sender:
        raise RuntimeError(
            "EMAIL_FROM not configured. Set this environment variable to a "
            "verified SES sender address."
        )
    if not recipients:
        raise RuntimeError(
            "EMAIL_TO not configured. Set this environment variable to "
            "comma-separated recipient email addresses."
        )

    # Build MIME message
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

    # Send via SES
    try:
        ses = _get_ses_client()
        response = ses.send_raw_email(
            Source=sender,
            Destinations=recipients,
            RawMessage={"Data": msg.as_string()}
        )
        
        message_id = response.get("MessageId", "unknown")
        logger.info(
            f"Email sent successfully via SES to {', '.join(recipients)} "
            f"(MessageId: {message_id})"
            f"{f' with {attachment_count} attachment(s)' if attachment_count else ''}"
        )
        
    except Exception as exc:
        error_msg = str(exc)
        
        # Provide helpful error messages for common SES issues
        if "Email address is not verified" in error_msg:
            raise RuntimeError(
                f"SES sender address not verified: {sender}. "
                "Go to AWS SES Console → Verified identities → Verify a new email address. "
                f"Error: {exc}"
            ) from exc
        elif "MessageRejected" in error_msg and "sandbox" in error_msg.lower():
            raise RuntimeError(
                f"SES is in sandbox mode - recipient addresses must be verified. "
                "Go to AWS SES Console → Verified identities to verify recipients, "
                "or request production access. "
                f"Error: {exc}"
            ) from exc
        elif "AccessDenied" in error_msg or "not authorized" in error_msg:
            raise RuntimeError(
                "Lambda IAM role lacks SES permissions. Add ses:SendEmail and "
                "ses:SendRawEmail permissions to the Lambda execution role. "
                f"Error: {exc}"
            ) from exc
        else:
            raise RuntimeError(f"Failed to send email via SES: {exc}") from exc


def send_test(to_addr: str) -> None:
    """Send a test email to verify SES configuration.
    
    Args:
        to_addr: Email address to send test to
    """
    when = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    sender = os.getenv("EMAIL_FROM") or "unknown"
    
    subject = "IBM Daily Digest — SES Test Email"
    html = (
        '<div style="font-family:Helvetica,Arial,sans-serif;font-size:14px;color:#161616;">'
        '<p style="font-size:16px;font-weight:700;color:#0F62FE;">&#9989; SES deployment test successful</p>'
        '<p>If you can read this, the IBM Daily Digest can deliver mail from AWS Lambda via SES.</p>'
        f'<p style="font-size:12px;color:#525252;">Method: <b>Amazon SES</b><br>'
        f'From: <b>{sender}</b><br>Sent: {when}</p></div>'
    )
    text = (
        f"SES deployment test successful. "
        f"Method: Amazon SES. From: {sender}. Sent: {when}."
    )
    
    send_digest(subject, html, text, attachments=None, recipients=[to_addr])
    logger.info(f"Test email sent to {to_addr} via SES")
