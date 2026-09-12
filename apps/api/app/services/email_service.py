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


async def send_new_account_email(
    to: str, temporary_password: str, full_name: str | None = None
) -> bool:
    """Email an admin-created user their temporary password + first steps."""
    login_url = f"{settings.FRONTEND_URL.rstrip('/')}/login"
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    html = f"""
    <div style="font-family:system-ui,Arial,sans-serif;line-height:1.5">
      <h2>Welcome to RankPilot AI</h2>
      <p>{greeting}</p>
      <p>An account has been created for you. Sign in with the temporary
         password below — you'll be asked to set your own password on first
         login.</p>
      <p style="font-size:16px">
        <strong>Email:</strong> {to}<br/>
        <strong>Temporary password:</strong>
        <code style="font-size:18px;letter-spacing:1px">{temporary_password}</code>
      </p>
      <p><a href="{login_url}">Sign in to RankPilot AI</a></p>
      <p style="color:#666;font-size:13px">If you weren't expecting this email,
         you can safely ignore it.</p>
    </div>
    """
    return await send_email(to, "Your RankPilot AI account", html)


async def send_contact_email(
    name: str, email: str, message: str, company: str | None = None
) -> bool:
    """Forward a "request access" / contact-form submission to the team."""
    to = settings.CONTACT_EMAIL or settings.EMAIL_FROM
    company_line = f"<strong>Company:</strong> {company}<br/>" if company else ""
    html = f"""
    <div style="font-family:system-ui,Arial,sans-serif;line-height:1.5">
      <h2>New access request</h2>
      <p><strong>Name:</strong> {name}<br/>
         <strong>Email:</strong> {email}<br/>
         {company_line}</p>
      <p style="white-space:pre-wrap">{message}</p>
    </div>
    """
    return await send_email(to, f"Access request from {name}", html)
