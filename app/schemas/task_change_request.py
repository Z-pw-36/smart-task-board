from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from app.schemas.common import StrictSchema, TaskStatus

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TaskChangeRequestCreate(StrictSchema):
    """A typed, immutable change proposal captured at one task version."""

    expected_task_version: int = Field(ge=1)
    patch_json: dict[str, Any] = Field(min_length=1)
    reason: NonBlankString

    @field_validator("patch_json")
    @classmethod
    def require_patch(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("patch_json must not be empty")
        return value


class TaskChangeRequestDecisionRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    approval_comment: str | None = None


class TaskChangeRequestRejectRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    reason: NonBlankString


class CancelTaskChangeRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    reason: NonBlankString


class TaskChangeRequestResponse(StrictSchema):
    change_request_id: UUID
    task_id: UUID
    requester_employee_no: str
    patch_json: dict[str, Any]
    reason: str
    before_snapshot: dict[str, Any]
    after_snapshot: dict[str, Any]
    status: str
    decision_by_employee_no: str | None
    decision_at: datetime | None
    decision_comment: str | None
    cancelled_by_employee_no: str | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    requester_task_version: int
    base_task_version: int
    created_at: datetime


class PaginatedTaskChangeRequestResponse(StrictSchema):
    items: list[TaskChangeRequestResponse]
    limit: int
    offset: int
    total: int


class TaskLifecycleActionResponse(StrictSchema):
    task_id: UUID
    status: TaskStatus
    task_version: int
    updated_at: datetime


class TaskChangeRequestActionResponse(TaskLifecycleActionResponse):
    change_request: TaskChangeRequestResponse


class MergeTaskRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    target_task_id: UUID
    reason: NonBlankString


class RestoreTaskRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    reason: NonBlankString
