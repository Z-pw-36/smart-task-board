from uuid import UUID

from app.schemas.common import StrictSchema


class CurrentUserDepartmentResponse(StrictSchema):
    department_id: UUID
    department_name: str


class CurrentUserResponse(StrictSchema):
    employee_no: str
    name: str
    department: CurrentUserDepartmentResponse | None
    role_type: str
    auth_mode: str
