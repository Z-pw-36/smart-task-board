from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.api.errors import AuthenticationRequiredError, register_exception_handlers
from app.services.errors import (
    BusinessValidationError,
    DependencyCycleError,
    DependencyNotSatisfiedError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    PermissionDeniedError,
    TaskVersionConflictError,
)

ERRORS = [
    (EntityNotFoundError("missing"), 404, "entity_not_found"),
    (PermissionDeniedError("denied"), 403, "permission_denied"),
    (InvalidStateTransitionError("state"), 409, "invalid_state_transition"),
    (TaskVersionConflictError("version"), 409, "task_version_conflict"),
    (BusinessValidationError("business"), 422, "business_validation_error"),
    (DependencyNotSatisfiedError("dependency"), 409, "dependency_not_satisfied"),
    (DependencyCycleError("cycle"), 422, "dependency_cycle"),
]


class Body(BaseModel):
    value: int


@pytest.fixture
def error_client() -> Iterator[TestClient]:
    application = FastAPI()
    register_exception_handlers(application)

    @application.get("/business/{index}")
    def business(index: int) -> None:
        raise ERRORS[index][0]

    @application.get("/auth")
    def auth() -> None:
        raise AuthenticationRequiredError

    @application.post("/validation")
    def validation(_body: Body) -> None:
        return None

    @application.get("/unique")
    def unique() -> None:
        class UniqueViolation(Exception):
            sqlstate = "23505"

        raise IntegrityError("SECRET SQL", {}, UniqueViolation("secret constraint"))

    @application.get("/unknown")
    def unknown() -> None:
        raise RuntimeError("database_url=postgresql://admin:secret@private")

    with TestClient(application, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize("index,error", tuple(enumerate(ERRORS)))
def test_business_error_mapping(
    error_client: TestClient,
    index: int,
    error: tuple[Exception, int, str],
) -> None:
    response = error_client.get(f"/business/{index}")

    assert response.status_code == error[1]
    assert response.json()["error"]["code"] == error[2]
    assert response.json()["error"]["details"] == {}


def test_authentication_and_request_validation_are_unified(
    error_client: TestClient,
) -> None:
    auth = error_client.get("/auth")
    validation = error_client.post("/validation", json={"value": "bad"})

    assert (auth.status_code, auth.json()["error"]["code"]) == (
        401,
        "authentication_required",
    )
    assert (validation.status_code, validation.json()["error"]["code"]) == (
        422,
        "request_validation_error",
    )


def test_integrity_and_unknown_errors_are_sanitized(error_client: TestClient) -> None:
    unique = error_client.get("/unique")
    unknown = error_client.get("/unknown")

    assert (unique.status_code, unique.json()["error"]["code"]) == (
        409,
        "resource_conflict",
    )
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (
        500,
        "internal_server_error",
    )
    combined = unique.text + unknown.text
    assert "SECRET SQL" not in combined
    assert "admin:secret" not in combined
    assert "database_url" not in combined
