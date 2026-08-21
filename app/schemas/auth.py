from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from app.schemas.common import StrictSchema

EmployeeNo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PrototypeUserResponse(StrictSchema):
    employee_no: str
    name: str
    department_id: UUID | None
    department_name: str | None
    role_type: str


class PrototypeLoginRequest(StrictSchema):
    employee_no: EmployeeNo


class PrototypeLoginUserResponse(StrictSchema):
    employee_no: str
    name: str


class PrototypeLoginResponse(StrictSchema):
    access_token: str = Field(repr=False)
    token_type: str = "bearer"
    expires_in: int
    user: PrototypeLoginUserResponse


class RefreshTokenRequest(StrictSchema):
    refresh_token: EmployeeNo


class TokenResponse(StrictSchema):
    access_token: str = Field(repr=False)
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str = Field(repr=False)
