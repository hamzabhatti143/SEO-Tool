"""Email notifications via Resend (https://resend.com).

Uses the Resend REST API over httpx (no SDK dependency). Best-effort: if no
API key is configured, emails are logged and skipped rather than failing the
calling automation job.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.resend.com/emails"


def is_configured() -> bool:
    return settings.EMAIL_PROVIDER == "resend" and bool(settings.RESEND_API_KEY)


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send an email. Returns True on success, False if skipped/failed."""
    if not to:
        return False
    if not is_configured():
        logger.info("Email skipped (provider not configured): %s", subject)
        return False
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                _ENDPOINT,
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.EMAIL_FROM,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
        if resp.status_code >= 400:
            logger.warning("Email send failed (%s): %s", resp.status_code, subject)
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning("Email send error: %s", exc)
        return False
