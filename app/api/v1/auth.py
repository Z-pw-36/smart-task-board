from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_identity_service
from app.core.config import Settings, get_settings
from app.schemas.auth import (
    PrototypeLoginRequest,
    PrototypeLoginResponse,
    PrototypeLoginUserResponse,
    PrototypeUserResponse,
)
from app.services.identity import PROTOTYPE_WARNING, IdentityService

router = APIRouter(prefix="/auth", tags=["prototype-auth"])
Identity = Annotated[IdentityService, Depends(get_identity_service)]
AppSettings = Annotated[Settings, Depends(get_settings)]


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
