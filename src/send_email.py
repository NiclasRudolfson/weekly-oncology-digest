"""
Send the digest via Gmail SMTP.

Setup (one-time):
  1. On your Google account: Security → 2-Step Verification → enable it
  2. Security → App passwords → create one for "Mail"
  3. Store the 16-char password as SMTP_PASSWORD in your env / GitHub secret

The module supports sending to multiple recipients (comma-separated in
RECIPIENT_EMAILS env var).
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send_digest(html: str, subject: str) -> None:
    """
    Send the HTML digest to all configured recipients.

    Args:
        html:    Full HTML email body
        subject: Email subject line
    """
    if not config.RECIPIENT_EMAILS:
        raise ValueError("RECIPIENT_EMAILS is not configured.")
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        raise ValueError("SMTP_USER and SMTP_PASSWORD must be set.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = config.SENDER_EMAIL or config.SMTP_USER
    msg["To"]      = ", ".join(config.RECIPIENT_EMAILS)

    # Plain-text fallback (stripped-down version)
    plain = _html_to_plain(html)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(
            from_addr=config.SENDER_EMAIL or config.SMTP_USER,
            to_addrs=config.RECIPIENT_EMAILS,
            msg=msg.as_string(),
        )

    print(f"  Email sent to: {', '.join(config.RECIPIENT_EMAILS)}")


def _html_to_plain(html: str) -> str:
    """Minimal HTML → plain-text conversion for the fallback part."""
    import re
    # Remove style/script blocks
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL)
    # Replace block elements with newlines
    text = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    for entity, char in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                          ("&gt;", ">"), ("&#8599;", "↗"), ("&middot;", "·")]:
        text = text.replace(entity, char)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
