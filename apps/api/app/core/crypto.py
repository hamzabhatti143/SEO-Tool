"""Symmetric encryption for stored third-party secrets (Fernet).

Platform credentials (WordPress API keys, Shopify access tokens) are stored
encrypted at rest. We use Fernet (AES-128-CBC + HMAC) from ``cryptography``.

The key comes from ``settings.CREDENTIALS_ENCRYPTION_KEY`` when set (it must be
a valid 32-byte url-safe base64 Fernet key). If it's empty we derive a stable
key from ``SECRET_KEY`` so encryption works out of the box in development —
**set a dedicated key in production** so rotating the JWT secret doesn't make
stored credentials undecryptable.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    configured = settings.CREDENTIALS_ENCRYPTION_KEY.strip()
    if configured:
        key = configured.encode()
    else:
        # Derive a valid Fernet key deterministically from SECRET_KEY.
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Encrypt a secret, returning a url-safe token string for storage."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a stored token back to plaintext.

    Raises ``InvalidToken`` if the ciphertext is corrupt or the key changed.
    """
    return _fernet().decrypt(token.encode()).decode()


__all__ = ["encrypt", "decrypt", "InvalidToken"]
