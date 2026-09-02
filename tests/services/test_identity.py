from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    InvalidPrototypeTokenError,
    create_access_token,
    decode_access_token,
)
from app.models import User
from app.services.errors import EntityNotFoundError, PermissionDeniedError
from app.services.identity import IdentityService


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://test:test@localhost/test",
        "auth_mode": "prototype",
        "prototype_auth_enabled": True,
        "prototype_user_employee_nos": "E-ONE,E-TWO",
        "jwt_secret_key": "prototype-test-secret-with-at-least-32-characters",
        "jwt_issuer": "test-issuer",
        "jwt_audience": "test-audience",
        "jwt_expire_minutes": 30,
        "allow_test_employee_header": False,
    }
    values.update(overrides)
    return Settings(**values)


def _encode(payload: dict[str, object], settings: Settings) -> str:
    assert settings.jwt_secret_key is not None
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def test_jwt_is_short_lived_and_round_trips_subject() -> None:
    settings = _settings()
    token, expires_in = create_access_token("E-ONE", settings)
    assert expires_in == 1800
    assert decode_access_token(token, settings) == "E-ONE"
    assert token not in repr(settings)


def test_jwt_rejects_tampering_expiration_issuer_and_audience() -> None:
    settings = _settings()
    token, _ = create_access_token("E-ONE", settings)
    with pytest.raises(InvalidPrototypeTokenError):
        decode_access_token(token + "tampered", settings)

    expired, _ = create_access_token(
        "E-ONE",
        settings,
        now=datetime.now(UTC) - timedelta(hours=2),
    )
    with pytest.raises(InvalidPrototypeTokenError):
        decode_access_token(expired, settings)
    with pytest.raises(InvalidPrototypeTokenError):
        decode_access_token(token, _settings(jwt_issuer="wrong"))
    with pytest.raises(InvalidPrototypeTokenError):
        decode_access_token(token, _settings(jwt_audience="wrong"))


@pytest.mark.parametrize("subject", [None, "", "   "])
def test_jwt_rejects_missing_or_blank_subject(subject: object) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    if subject is not None:
        payload["sub"] = subject
    token = _encode(payload, settings)
    with pytest.raises(InvalidPrototypeTokenError):
        decode_access_token(token, settings)


def test_identity_lists_only_allowlisted_active_users_in_configured_order() -> None:
    service = IdentityService(MagicMock())
    service._users = MagicMock()
    active = User(employee_no="E-ONE", name="One", role_type="employee", status="active")
    disabled = User(employee_no="E-TWO", name="Two", role_type="employee", status="disabled")
    service._users.list_by_employee_nos.return_value = [disabled, active]
    assert service.list_prototype_users(_settings()) == [active]


def test_login_is_uniformly_rejected_for_non_allowlisted_missing_or_disabled_user() -> None:
    service = IdentityService(MagicMock())
    service._users = MagicMock()
    settings = _settings()
    with pytest.raises(PermissionDeniedError, match="prototype login failed"):
        service.prototype_login("E-OUTSIDE", settings)
    service._users.get_by_employee_no_with_department.return_value = None
    with pytest.raises(PermissionDeniedError, match="prototype login failed"):
        service.prototype_login("E-ONE", settings)
    disabled = User(employee_no="E-ONE", name="One", role_type="employee", status="disabled")
    service._users.get_by_employee_no_with_department.return_value = disabled
    with pytest.raises(PermissionDeniedError, match="prototype login failed"):
        service.prototype_login("E-ONE", settings)


def test_prototype_endpoints_are_unavailable_when_mode_is_disabled() -> None:
    service = IdentityService(MagicMock())
    settings = Settings(
        database_url="postgresql+psycopg://test:test@localhost/test",
        auth_mode="disabled",
        allow_test_employee_header=False,
    )
    with pytest.raises(EntityNotFoundError):
        service.list_prototype_users(settings)


def test_current_user_permissions_are_backend_projection() -> None:
    service = IdentityService(MagicMock())
    employee = User(
        employee_no="E-EMPLOYEE",
        name="Employee",
        role_type="employee",
        status="active",
    )
    executive = User(
        employee_no="E-EXECUTIVE",
        name="Executive",
        role_type="executive",
        status="active",
    )
    admin = User(employee_no="E-ADMIN", name="Admin", role_type="admin", status="active")
    department_scope = SimpleNamespace(
        scope_type="department",
        scope_id="D-1",
        permission_type="view",
    )
    all_data_scope = SimpleNamespace(
        scope_type="all_demo_data",
        scope_id=None,
        permission_type="view",
    )

    assert service.current_user_permissions(employee, [])["can_access_executive"] is False
    assert service.current_user_permissions(executive, [])["can_access_executive"] is True
    assert service.current_user_permissions(employee, [department_scope])[
        "can_access_executive"
    ] is True
    assert service.current_user_permissions(employee, [all_data_scope])[
        "can_view_all_demo_data"
    ] is True
    assert service.current_user_permissions(admin, [])["can_manage_permissions"] is True


def test_production_rejects_prototype_and_test_header_modes() -> None:
    with pytest.raises(ValueError, match="forbidden in production"):
        _settings(app_env="production")
    with pytest.raises(ValueError, match="forbidden in production"):
        Settings(
            database_url="postgresql+psycopg://test:test@localhost/test",
            app_env="production",
            auth_mode="test_header",
            allow_test_employee_header=True,
        )
