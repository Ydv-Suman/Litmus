"""
Send transactional email via SendGrid.

Set in backend/.env (optional — if unset, callers should skip or surface the link in API only):
  SENDGRID_API_KEY=...
  SENDGRID_FROM_EMAIL=your-verified-sender@domain.com
  SENDGRID_FROM_NAME=Litmus Hiring
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _sendgrid_configured() -> bool:
    return bool(
        os.environ.get("SENDGRID_API_KEY", "").strip()
        and os.environ.get("SENDGRID_FROM_EMAIL", "").strip()
    )


def send_html_email(
    *,
    to_address: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> bool:
    """
    Returns True if send succeeded, False if SendGrid is not configured or send failed
    (failure is logged; does not raise).
    """
    if not _sendgrid_configured():
        logger.warning("SendGrid not configured; skipping email to %s", to_address)
        return False

    api_key = os.environ["SENDGRID_API_KEY"].strip()
    from_email = os.environ["SENDGRID_FROM_EMAIL"].strip()
    from_name = os.environ.get("SENDGRID_FROM_NAME", "Litmus Hiring").strip()
    plain = text_body or "Open this email in HTML view."

    payload: dict[str, Any] = {
        "personalizations": [{"to": [{"email": to_address}]}],
        "from": {"email": from_email, "name": from_name},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": plain},
            {"type": "text/html", "value": html_body},
        ],
    }

    try:
        from sendgrid import SendGridAPIClient

        client = SendGridAPIClient(api_key)
        response = client.client.mail.send.post(request_body=payload)
        if response.status_code >= 400:
            logger.error(
                "SendGrid rejected email to %s (status=%s, body=%r)",
                to_address,
                response.status_code,
                getattr(response, "body", b""),
            )
            return False
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_address)
        return False
