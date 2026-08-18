from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

import app.api.dependencies as dependencies
from app.api.dependencies import get_identity_service
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.main import app
from app.services.errors import PermissionDeniedError


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://test:test@localhost/test",
        auth_mode="prototype",
        prototype_auth_enabled=True,
        prototype_user_employee_nos="E-CREATOR",
        jwt_secret_key="prototype-test-secret-with-at-least-32-characters",
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        allow_test_employee_header=False,
    )


def test_current_user_uses_bearer_subject_and_returns_department(monkeypatch) -> None:
    settings = _settings()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    department = SimpleNamespace(
        department_id=uuid4(), department_name="Demo Department"
    )
    user = SimpleNamespace(
        employee_no="E-CREATOR",
        name="Demo Creator",
        department=department,
        role_type="employee",
        status="active",
    )
    service = MagicMock()
    service.get_active_user.return_value = user
    app.dependency_overrides[get_identity_service] = lambda: service
    app.dependency_overrides[get_settings] = lambda: settings
    token, _ = create_access_token("E-CREATOR", settings)
    try:
        response = TestClient(app).get(
            "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {
        "employee_no": "E-CREATOR",
        "name": "Demo Creator",
        "department": {
            "department_id": str(department.department_id),
            "department_name": "Demo Department",
        },
        "role_type": "employee",
        "auth_mode": "prototype",
    }
    service.get_active_user.assert_called_once_with("E-CREATOR")


def test_current_user_rejects_unknown_or_disabled_identity(monkeypatch) -> None:
    settings = _settings()
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    service = MagicMock()
    service.get_active_user.side_effect = PermissionDeniedError(
        "current identity is unavailable"
    )
    app.dependency_overrides[get_identity_service] = lambda: service
    app.dependency_overrides[get_settings] = lambda: settings
    token, _ = create_access_token("E-CREATOR", settings)
    try:
        response = TestClient(app).get(
            "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403
    assert "database" not in response.text.casefold()
