"""Password hashing and JWT helpers."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

# Scope claim that distinguishes a super-admin token from a regular user
# token. Regular user tokens never carry this scope, and admin tokens carry
# a username (not a user UUID) as ``sub`` — so the two can never be confused.
ADMIN_SCOPE = "admin"

# Unambiguous alphabet for temporary passwords (no 0/O/1/l/I) so they are
# easy to read and type when shared manually by an admin.
_TEMP_PW_ALPHABET = (
    "ABCDEFGHJKLMNPQRSTUVWXYZ" "abcdefghijkmnopqrstuvwxyz" "23456789"
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def generate_temp_password(length: int = 14) -> str:
    """Generate a cryptographically secure, human-shareable temp password."""
    return "".join(secrets.choice(_TEMP_PW_ALPHABET) for _ in range(length))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str | uuid.UUID, expires_delta: timedelta | None = None
) -> str:
    """Create a signed HS256 JWT with ``sub`` set to the user id."""
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_admin_token(
    subject: str, expires_delta: timedelta | None = None
) -> str:
    """Create a signed admin JWT carrying the distinct ``admin`` scope claim."""
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.ADMIN_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "scope": ADMIN_SCOPE,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises ``JWTError`` on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


__all__ = [
    "hash_password",
    "verify_password",
    "generate_temp_password",
    "create_access_token",
    "create_admin_token",
    "decode_access_token",
    "ADMIN_SCOPE",
    "JWTError",
]
