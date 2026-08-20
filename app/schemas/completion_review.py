from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from app.schemas.common import StrictSchema, TaskStatus

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type CompletionReviewStatus = Literal["submitted", "approved", "rejected"]
type CompletionReviewResult = Literal["approved", "rejected"]


class SubmitCompletionRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    completion_note: NonBlankString
    deliverable_summary: NonBlankString


class CompletionDecisionRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    completion_review_id: UUID


class RejectCompletionRequest(CompletionDecisionRequest):
    reject_reason: NonBlankString
    rework_node_id: UUID | None = None


class ReopenNodeRequest(CompletionDecisionRequest):
    pass


class CompletionReviewResponse(StrictSchema):
    completion_review_id: UUID
    task_id: UUID
    review_round: int
    submitted_by_employee_no: str
    completion_note: str | None
    deliverable_summary: str | None
    reviewer_employee_no: str
    review_status: CompletionReviewStatus
    review_result: CompletionReviewResult | None
    reject_reason: str | None
    rework_node_id: UUID | None
    submitted_task_version: int
    reviewed_task_version: int | None
    submitted_at: datetime
    reviewed_at: datetime | None
    is_legacy_import: bool


class CompletionReviewActionResponse(StrictSchema):
    task_id: UUID
    status: TaskStatus
    task_version: int
    updated_at: datetime
    review: CompletionReviewResponse


class PaginatedCompletionReviewResponse(StrictSchema):
    items: list[CompletionReviewResponse]
    limit: int
    offset: int
    total: int
