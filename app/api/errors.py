from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.services.errors import (
    BusinessValidationError,
    DependencyCycleError,
    DependencyNotSatisfiedError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    OpenTaskIssueConflictError,
    PermissionDeniedError,
    TaskVersionConflictError,
    WorkflowError,
)


class AuthenticationRequiredError(Exception):
    pass


def _response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


_WORKFLOW_ERRORS: dict[type[WorkflowError], tuple[int, str]] = {
    EntityNotFoundError: (404, "entity_not_found"),
    PermissionDeniedError: (403, "permission_denied"),
    InvalidStateTransitionError: (409, "invalid_state_transition"),
    TaskVersionConflictError: (409, "task_version_conflict"),
    BusinessValidationError: (422, "business_validation_error"),
    DependencyNotSatisfiedError: (409, "dependency_not_satisfied"),
    DependencyCycleError: (422, "dependency_cycle"),
    OpenTaskIssueConflictError: (409, "open_task_issue_conflict"),
}


async def authentication_error_handler(
    _request: Request,
    _exc: AuthenticationRequiredError,
) -> JSONResponse:
    return _response(401, "authentication_required", "X-Employee-No is required")


async def workflow_error_handler(
    _request: Request,
    exc: WorkflowError,
) -> JSONResponse:
    status_code, code = _WORKFLOW_ERRORS.get(
        type(exc),
        (422, "business_validation_error"),
    )
    return _response(status_code, code, str(exc))


async def validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = [
        {
            "type": item.get("type", "validation_error"),
            "location": [str(value) for value in item.get("loc", ())],
            "message": item.get("msg", "Invalid request"),
        }
        for item in exc.errors()
    ]
    return _response(
        422,
        "request_validation_error",
        "Request validation failed",
        {"errors": errors},
    )


async def integrity_error_handler(
    _request: Request,
    exc: IntegrityError,
) -> JSONResponse:
    sqlstate = getattr(exc.orig, "sqlstate", None)
    if sqlstate == "23505":
        return _response(409, "resource_conflict", "Resource already exists")
    return _response(500, "internal_server_error", "Internal server error")


async def unexpected_error_handler(
    _request: Request,
    _exc: Exception,
) -> JSONResponse:
    return _response(500, "internal_server_error", "Internal server error")


ExceptionHandler = Callable[[Request, Any], Awaitable[JSONResponse]]


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthenticationRequiredError, authentication_error_handler)
    app.add_exception_handler(WorkflowError, workflow_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
