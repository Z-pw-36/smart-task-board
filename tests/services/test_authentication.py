from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models import RefreshToken, User
from app.services import PermissionDeniedError
from app.services import authentication as authentication_module
from app.services.authentication import AuthenticationService

NOW = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://test:test@localhost/test",
        auth_mode="prototype",
        prototype_auth_enabled=True,
        prototype_user_employee_nos="E-ONE",
        jwt_secret_key="prototype-test-secret-with-at-least-32-characters",
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        allow_test_employee_header=False,
    )


class RecordingSession:
    def __init__(
        self,
        *,
        user: User | None = None,
        refresh_token: RefreshToken | None = None,
    ) -> None:
        self.user = user
        self.refresh_token = refresh_token
        self.added: list[object] = []
        self.commits = 0

    def get(self, model, key):
        if model is User and self.user is not None and key == self.user.employee_no:
            return self.user
        return None

    def scalar(self, _statement):
        return self.refresh_token

    def add(self, row: object) -> None:
        self.added.append(row)

    def flush(self) -> None:
        for row in self.added:
            if isinstance(row, RefreshToken) and row.refresh_token_id is None:
                row.refresh_token_id = uuid4()

    def commit(self) -> None:
        self.commits += 1


def test_issue_persists_only_hashed_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authentication_module, "_now", lambda: NOW)
    monkeypatch.setattr(authentication_module.secrets, "token_urlsafe", lambda _size: "raw-token")
    session = RecordingSession(
        user=User(employee_no="E-ONE", name="One", role_type="employee", status="active")
    )

    result = AuthenticationService(session, _settings()).issue(
        "E-ONE", client_id="web", user_agent="pytest"
    )

    row = next(item for item in session.added if isinstance(item, RefreshToken))
    assert result["refresh_token"] == "raw-token"
    assert row.token_hash == hashlib.sha256(b"raw-token").hexdigest()
    assert row.token_hash != result["refresh_token"]
    assert row.employee_no == "E-ONE"
    assert row.client_id == "web"
    assert row.user_agent == "pytest"
    assert row.issued_at == NOW
    assert row.expires_at == NOW + timedelta(days=30)
    assert session.commits == 1


def test_rotate_marks_current_token_and_issues_same_family_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authentication_module, "_now", lambda: NOW)
    monkeypatch.setattr(authentication_module.secrets, "token_urlsafe", lambda _size: "next-token")
    family_id = uuid4()
    current = RefreshToken(
        refresh_token_id=uuid4(),
        employee_no="E-ONE",
        token_hash=hashlib.sha256(b"current-token").hexdigest(),
        family_id=family_id,
        status="active",
        issued_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=1),
        client_id="web",
        user_agent="old-agent",
    )
    session = RecordingSession(
        user=User(employee_no="E-ONE", name="One", role_type="employee", status="active"),
        refresh_token=current,
    )

    result = AuthenticationService(session, _settings()).rotate(
        "current-token", user_agent="new-agent"
    )

    replacement = next(item for item in session.added if isinstance(item, RefreshToken))
    assert result["refresh_token"] == "next-token"
    assert current.status == "rotated"
    assert current.rotated_at == NOW
    assert current.replaced_by_token_id == replacement.refresh_token_id
    assert replacement.family_id == family_id
    assert replacement.client_id == "web"
    assert replacement.user_agent == "new-agent"
    assert replacement.token_hash == hashlib.sha256(b"next-token").hexdigest()
    assert session.commits == 1


def test_rotate_expires_stale_token_and_rejects_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authentication_module, "_now", lambda: NOW)
    expired = RefreshToken(
        employee_no="E-ONE",
        token_hash=hashlib.sha256(b"expired-token").hexdigest(),
        family_id=uuid4(),
        status="active",
        issued_at=NOW - timedelta(days=31),
        expires_at=NOW - timedelta(seconds=1),
    )
    session = RecordingSession(refresh_token=expired)

    with pytest.raises(PermissionDeniedError, match="refresh token is invalid"):
        AuthenticationService(session, _settings()).rotate("expired-token")

    assert expired.status == "expired"
    assert session.commits == 1


def test_revoke_marks_active_token_without_exposing_raw_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(authentication_module, "_now", lambda: NOW)
    row = RefreshToken(
        employee_no="E-ONE",
        token_hash=hashlib.sha256(b"active-token").hexdigest(),
        family_id=uuid4(),
        status="active",
        issued_at=NOW,
        expires_at=NOW + timedelta(days=1),
    )
    session = RecordingSession(refresh_token=row)

    AuthenticationService(session, _settings()).revoke("active-token")

    assert row.status == "revoked"
    assert row.revoked_at == NOW
    assert session.commits == 1
