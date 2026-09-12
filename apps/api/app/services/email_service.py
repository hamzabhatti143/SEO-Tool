"""Email notifications.

Providers, selected by ``settings.EMAIL_PROVIDER``:

  * ``gmail``    — send via the Gmail API using a Google OAuth client
    (client id/secret + refresh token). True per-recipient delivery with rich
    HTML, sent from ``GMAIL_SENDER``.
  * ``formspree`` — POST to the configured Formspree form endpoint. Formspree
    delivers to the address set up on that form (form-to-email), so it is NOT
    per-recipient.
  * ``resend``   — the Resend transactional API (per-recipient delivery).

Best-effort: if nothing is configured, emails are logged and skipped rather
than failing the calling job.
"""

from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RESEND_ENDPOINT = "https://api.resend.com/emails"
_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_GMAIL_SEND_ENDPOINT = (
    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
)


def _gmail_ready() -> bool:
    return all(
        (
            settings.GMAIL_CLIENT_ID,
            settings.GMAIL_CLIENT_SECRET,
            settings.GMAIL_REFRESH_TOKEN,
            settings.GMAIL_SENDER,
        )
    )


def is_configured() -> bool:
    if settings.EMAIL_PROVIDER == "gmail":
        return _gmail_ready()
    if settings.EMAIL_PROVIDER == "formspree":
        return bool(settings.FORMSPREE_ENDPOINT)
    if settings.EMAIL_PROVIDER == "resend":
        return bool(settings.RESEND_API_KEY)
    return False


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send an email. Returns True on success, False if skipped/failed."""
    if not to:
        return False
    if settings.EMAIL_PROVIDER == "gmail" and _gmail_ready():
        return await _send_via_gmail(to, subject, html)
    if settings.EMAIL_PROVIDER == "formspree" and settings.FORMSPREE_ENDPOINT:
        return await _send_via_formspree(to, subject, html)
    if settings.EMAIL_PROVIDER == "resend" and settings.RESEND_API_KEY:
        return await _send_via_resend(to, subject, html)
    logger.info("Email skipped (provider not configured): %s", subject)
    return False


async def _gmail_access_token(client: httpx.AsyncClient) -> str | None:
    """Exchange the stored refresh token for a short-lived access token."""
    resp = await client.post(
        _GOOGLE_TOKEN_ENDPOINT,
        data={
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "refresh_token": settings.GMAIL_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
    )
    if resp.status_code >= 400:
        logger.warning("Gmail token refresh failed (%s)", resp.status_code)
        return None
    return resp.json().get("access_token")


async def _send_via_gmail(to: str, subject: str, html: str) -> bool:
    """Send an HTML email via the Gmail API (OAuth client credentials)."""
    message = MIMEText(html, "html", "utf-8")
    message["To"] = to
    message["From"] = settings.EMAIL_FROM or settings.GMAIL_SENDER
    message["Subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            token = await _gmail_access_token(client)
            if not token:
                return False
            resp = await client.post(
                _GMAIL_SEND_ENDPOINT,
                headers={"Authorization": f"Bearer {token}"},
                json={"raw": raw},
            )
        if resp.status_code >= 400:
            logger.warning(
                "Gmail send failed (%s): %s", resp.status_code, subject
            )
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning("Gmail send error: %s", exc)
        return False


async def _send_via_formspree(to: str, subject: str, html: str) -> bool:
    """POST the message to the Formspree form; it emails the form's inbox."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                settings.FORMSPREE_ENDPOINT,
                headers={"Accept": "application/json"},
                json={
                    # `email`/`_replyto` set the reply-to; Formspree still
                    # delivers to the form's configured address.
                    "email": to,
                    "_replyto": to,
                    "_subject": subject,
                    "subject": subject,
                    "intended_recipient": to,
                    "message": html,
                },
            )
        if resp.status_code >= 400:
            logger.warning(
                "Formspree send failed (%s): %s", resp.status_code, subject
            )
            return False
        return True
    except httpx.HTTPError as exc:
        logger.warning("Formspree send error: %s", exc)
        return False


async def _send_via_resend(to: str, subject: str, html: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                _RESEND_ENDPOINT,
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
