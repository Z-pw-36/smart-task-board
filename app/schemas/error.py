from typing import Any

from app.schemas.common import StrictSchema


class ErrorDetail(StrictSchema):
    code: str
    message: str
    details: dict[str, Any]


class ErrorResponse(StrictSchema):
    error: ErrorDetail
