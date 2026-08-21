from typing import Annotated

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import (
    get_authentication_service,
    get_current_employee_no,
    get_identity_service,
)
from app.core.config import Settings, get_settings
from app.models import User
from app.schemas.auth import (
    PrototypeLoginRequest,
    PrototypeLoginResponse,
    PrototypeLoginUserResponse,
    PrototypeUserResponse,
    RefreshTokenRequest,
    TokenResponse,
)
from app.services.authentication import AuthenticationService
from app.services.identity import PROTOTYPE_WARNING, IdentityService

router = APIRouter(prefix="/auth", tags=["prototype-auth"])
Identity = Annotated[IdentityService, Depends(get_identity_service)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AuthService = Annotated[AuthenticationService, Depends(get_authentication_service)]
Actor = Annotated[str, Depends(get_current_employee_no)]


@router.get(
    "/prototype-users",
    response_model=list[PrototypeUserResponse],
    summary="List allow-listed isolated-demo users",
    description=PROTOTYPE_WARNING,
)
def list_prototype_users(
    service: Identity,
    settings: AppSettings,
) -> list[PrototypeUserResponse]:
    return [
        PrototypeUserResponse(
            employee_no=user.employee_no,
            name=user.name,
            department_id=user.department_id,
            department_name=user.department.department_name if user.department else None,
            role_type=user.role_type,
        )
        for user in service.list_prototype_users(settings)
    ]


@router.post(
    "/prototype-login",
    response_model=PrototypeLoginResponse,
    summary="Sign in as an allow-listed isolated-demo user",
    description=PROTOTYPE_WARNING,
)
def prototype_login(
    request: PrototypeLoginRequest,
    service: Identity,
    settings: AppSettings,
) -> PrototypeLoginResponse:
    user, token, expires_in = service.prototype_login(request.employee_no, settings)
    return PrototypeLoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=PrototypeLoginUserResponse(employee_no=user.employee_no, name=user.name),
    )


@router.post("/token", response_model=TokenResponse, summary="Issue access and refresh tokens")
def issue_tokens(
    request: PrototypeLoginRequest,
    service: AuthService,
    settings: AppSettings,
    user_agent: str | None = Header(default=None),
) -> TokenResponse:
    if settings.auth_mode == "prototype":
        user = service.session.get(User, request.employee_no)
        if (
            user is None
            or user.status != "active"
            or request.employee_no not in settings.prototype_employee_nos
        ):
            from app.services.errors import PermissionDeniedError

            raise PermissionDeniedError("authentication failed")
    result = service.issue(request.employee_no, user_agent=user_agent)
    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate a refresh token")
def refresh_tokens(
    request: RefreshTokenRequest,
    service: AuthService,
    user_agent: str | None = Header(default=None),
) -> TokenResponse:
    return TokenResponse(**service.rotate(request.refresh_token, user_agent=user_agent))


@router.post("/revoke", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a refresh token")
def revoke_token(request: RefreshTokenRequest, service: AuthService) -> None:
    service.revoke(request.refresh_token)


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke all sessions for an employee"
)
def logout(actor: Actor, service: AuthService) -> None:
    service.revoke_employee(actor)
