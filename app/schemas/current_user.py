from uuid import UUID

from app.schemas.common import StrictSchema


class CurrentUserDepartmentResponse(StrictSchema):
    department_id: UUID
    department_name: str


class CurrentUserScopeResponse(StrictSchema):
    authorized_scope_id: UUID
    scope_type: str
    scope_id: str | None
    permission_type: str


class CurrentUserPermissionsResponse(StrictSchema):
    can_access_executive: bool
    can_manage_permissions: bool
    can_view_all_demo_data: bool
    allowed_routes: list[str]
    capabilities: list[str]


class CurrentUserResponse(StrictSchema):
    employee_no: str
    name: str
    department: CurrentUserDepartmentResponse | None
    role_type: str
    roles: list[str]
    permissions: CurrentUserPermissionsResponse
    scopes: list[CurrentUserScopeResponse]
    auth_mode: str
