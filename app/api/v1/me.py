from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_employee_no, get_identity_service
from app.core.config import Settings, get_settings
from app.schemas.current_user import CurrentUserDepartmentResponse, CurrentUserResponse
from app.services.identity import IdentityService

router = APIRouter(tags=["current-user"])
Actor = Annotated[str, Depends(get_current_employee_no)]
Identity = Annotated[IdentityService, Depends(get_identity_service)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/me", response_model=CurrentUserResponse, summary="Get current user")
def get_current_user(
    actor: Actor,
    service: Identity,
    settings: AppSettings,
) -> CurrentUserResponse:
    user = service.get_active_user(actor)
    department = None
    if user.department is not None:
        department = CurrentUserDepartmentResponse(
            department_id=user.department.department_id,
            department_name=user.department.department_name,
        )
    return CurrentUserResponse(
        employee_no=user.employee_no,
        name=user.name,
        department=department,
        role_type=user.role_type,
        auth_mode=settings.auth_mode,
    )
