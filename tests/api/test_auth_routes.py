from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.dependencies as dependencies
from app.api.dependencies import get_identity_service
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.main import app, create_app
from app.services.errors import EntityNotFoundError, PermissionDeniedError


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://test:test@localhost/test",
        "auth_mode": "prototype",
        "prototype_auth_enabled": True,
        "prototype_user_employee_nos": "E-CREATOR,E-ASSIGNEE",
        "jwt_secret_key": "prototype-test-secret-with-at-least-32-characters",
        "jwt_issuer": "test-issuer",
        "jwt_audience": "test-audience",
        "allow_test_employee_header": False,
        "cors_allowed_origins": "http://localhost:5173",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def auth_context():
    settings = _settings()
    service = MagicMock()
    department = SimpleNamespace(
        department_id=uuid4(), department_name="Demo Department"
    )
    creator = SimpleNamespace(
        employee_no="E-CREATOR",
        name="Demo Creator",
        department_id=department.department_id,
        department=department,
        role_type="employee",
        status="active",
    )
    assignee = SimpleNamespace(
        employee_no="E-ASSIGNEE",
        name="Demo Assignee",
        department_id=department.department_id,
        department=department,
        role_type="employee",
        status="active",
    )
    service.list_prototype_users.return_value = [creator, assignee]
    token, expires_in = create_access_token("E-CREATOR", settings)
    service.prototype_login.return_value = (creator, token, expires_in)
    app.dependency_overrides[get_identity_service] = lambda: service
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield TestClient(app), service, settings, token
    finally:
        app.dependency_overrides.clear()


def test_prototype_user_list_returns_only_safe_summary(auth_context) -> None:
    client, service, _, _ = auth_context
    response = client.get("/api/v1/auth/prototype-users")
    assert response.status_code == 200
    assert [item["employee_no"] for item in response.json()] == [
        "E-CREATOR",
        "E-ASSIGNEE",
    ]
    assert set(response.json()[0]) == {
        "employee_no",
        "name",
        "department_id",
        "department_name",
        "role_type",
    }
    service.list_prototype_users.assert_called_once()


def test_prototype_login_returns_short_lived_bearer_without_logging_token(
    auth_context, caplog
) -> None:
    client, service, _, token = auth_context
    response = client.post(
        "/api/v1/auth/prototype-login", json={"employee_no": "E-CREATOR"}
    )
    assert response.status_code == 200
    assert response.json()["access_token"] == token
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 1800
    assert token not in caplog.text
    service.prototype_login.assert_called_once()


def test_prototype_login_failure_does_not_reveal_user_state(auth_context) -> None:
    client, service, _, _ = auth_context
    service.prototype_login.side_effect = PermissionDeniedError("prototype login failed")
    response = client.post(
        "/api/v1/auth/prototype-login", json={"employee_no": "E-UNKNOWN"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["message"] == "prototype login failed"
    assert "unknown" not in response.text.casefold()


def test_disabled_prototype_endpoint_returns_not_found(auth_context) -> None:
    client, service, _, _ = auth_context
    service.list_prototype_users.side_effect = EntityNotFoundError(
        "prototype authentication is unavailable"
    )
    response = client.get("/api/v1/auth/prototype-users")
    assert response.status_code == 404


def test_prototype_mode_ignores_employee_header_and_requires_bearer(
    auth_context, monkeypatch
) -> None:
    client, _, settings, _ = auth_context
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    response = client.get("/api/v1/me", headers={"X-Employee-No": "E-CREATOR"})
    assert response.status_code == 401


def test_cors_allows_only_configured_origin() -> None:
    client = TestClient(create_app(_settings()))
    allowed = client.options(
        "/api/v1/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    denied = client.options(
        "/api/v1/me",
        headers={
            "Origin": "https://untrusted.invalid",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers
