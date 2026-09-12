"""Tests for the isolated super-admin auth (env credentials + admin JWT)."""

import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.admin.deps import require_super_admin
from app.core import security
from app.core.config import settings
from app.main import app

client = TestClient(app)


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_admin_login_success(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SUPER_ADMIN_USERNAME", "root")
    monkeypatch.setattr(settings, "SUPER_ADMIN_PASSWORD", "s3cret")
    res = client.post(
        "/api/admin/login", json={"username": "root", "password": "s3cret"}
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    # Token carries the distinct admin scope.
    payload = security.decode_access_token(token)
    assert payload["scope"] == security.ADMIN_SCOPE
    assert payload["sub"] == "root"


def test_admin_login_rejects_bad_credentials(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SUPER_ADMIN_USERNAME", "root")
    monkeypatch.setattr(settings, "SUPER_ADMIN_PASSWORD", "s3cret")
    res = client.post(
        "/api/admin/login", json={"username": "root", "password": "wrong"}
    )
    assert res.status_code == 401


def test_admin_login_disabled_when_env_unset(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SUPER_ADMIN_USERNAME", "")
    monkeypatch.setattr(settings, "SUPER_ADMIN_PASSWORD", "")
    res = client.post(
        "/api/admin/login", json={"username": "", "password": ""}
    )
    assert res.status_code == 401


async def test_require_super_admin_accepts_admin_token() -> None:
    token = security.create_admin_token("root")
    assert await require_super_admin(credentials=_bearer(token)) == "root"


async def test_require_super_admin_rejects_regular_user_token() -> None:
    # A normal user token has no admin scope — must be rejected with 403.
    user_token = security.create_access_token(uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        await require_super_admin(credentials=_bearer(user_token))
    assert exc.value.status_code == 403


async def test_require_super_admin_rejects_missing_and_garbage() -> None:
    with pytest.raises(HTTPException) as exc:
        await require_super_admin(credentials=None)
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException):
        await require_super_admin(credentials=_bearer("not-a-jwt"))
