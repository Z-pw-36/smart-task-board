from datetime import UTC, datetime

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request

import app.api.dependencies as dependencies
from app.api.dependencies import get_current_employee_no
from app.api.errors import AuthenticationRequiredError
from app.core.config import Settings
from app.core.security import create_access_token


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://test:test@localhost/test",
        "auth_mode": "test_header",
        "allow_test_employee_header": True,
        "jwt_secret_key": "prototype-test-secret-with-at-least-32-characters",
        "jwt_issuer": "test-issuer",
        "jwt_audience": "test-audience",
    }
    values.update(overrides)
    return Settings(**values)


def _request(**headers: str) -> Request:
    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in headers.items()
    ]
    return Request({"type": "http", "headers": raw_headers})


def _credentials(token: str, scheme: str = "Bearer") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)


def test_employee_header_is_trimmed(monkeypatch) -> None:
    monkeypatch.setattr(dependencies, "get_settings", _settings)
    request = _request(**{"X-Employee-No": "  E001  "})

    assert get_current_employee_no(request) == "E001"


def test_valid_bearer_is_used_without_test_header(monkeypatch) -> None:
    settings = _settings(allow_test_employee_header=False, auth_mode="disabled")
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    token, _ = create_access_token("E-BEARER", settings, now=datetime.now(UTC))

    assert get_current_employee_no(
        _request(Authorization=f"Bearer {token}"),
        _credentials(token),
    ) == "E-BEARER"


def test_valid_bearer_takes_priority_over_different_test_header(monkeypatch) -> None:
    settings = _settings()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    token, _ = create_access_token("E-BEARER", settings, now=datetime.now(UTC))

    assert get_current_employee_no(
        _request(
            Authorization=f"Bearer {token}",
            **{"X-Employee-No": "E-HEADER"},
        ),
        _credentials(token),
    ) == "E-BEARER"


def test_invalid_bearer_does_not_fall_back_to_test_header(monkeypatch) -> None:
    settings = _settings()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    request = _request(
        Authorization="Bearer invalid-token",
        **{"X-Employee-No": "E-HEADER"},
    )

    with pytest.raises(AuthenticationRequiredError):
        get_current_employee_no(request, _credentials("invalid-token"))


def test_basic_scheme_does_not_fall_back_to_test_header(monkeypatch) -> None:
    monkeypatch.setattr(dependencies, "get_settings", _settings)
    request = _request(
        Authorization="Basic abc123",
        **{"X-Employee-No": "E-HEADER"},
    )

    with pytest.raises(AuthenticationRequiredError):
        get_current_employee_no(request)


def test_test_header_is_rejected_when_disabled(monkeypatch) -> None:
    settings = _settings(allow_test_employee_header=False, auth_mode="disabled")
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    with pytest.raises(AuthenticationRequiredError):
        get_current_employee_no(_request(**{"X-Employee-No": "E001"}))


@pytest.mark.parametrize("value", [None, "", "   "])
def test_employee_header_is_required(monkeypatch, value: str | None) -> None:
    monkeypatch.setattr(dependencies, "get_settings", _settings)
    headers = {} if value is None else {"X-Employee-No": value}

    with pytest.raises(AuthenticationRequiredError):
        get_current_employee_no(_request(**headers))
