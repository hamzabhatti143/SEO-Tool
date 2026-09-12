"""Super-admin authentication dependency (validates the admin JWT).

Isolated from ``app.api.deps`` (regular user auth): this never touches the
Users table. It only verifies that the bearer token is a well-formed admin
token carrying the ``admin`` scope claim.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import ADMIN_SCOPE, JWTError, decode_access_token

# Separate bearer scheme so the admin API documents its own auth and never
# shares the user OAuth2 password flow.
_admin_bearer = HTTPBearer(auto_error=False, scheme_name="AdminBearer")

_ADMIN_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Admin authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)


async def require_super_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_admin_bearer),
) -> str:
    """Return the admin username from a valid admin JWT, else 401.

    Rejects regular user tokens: those carry no ``admin`` scope.
    """
    if credentials is None:
        raise _ADMIN_CREDENTIALS_EXC
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise _ADMIN_CREDENTIALS_EXC from exc

    if payload.get("scope") != ADMIN_SCOPE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admin privileges are required.",
        )
    subject = payload.get("sub")
    if not subject:
        raise _ADMIN_CREDENTIALS_EXC
    return subject
