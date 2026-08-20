from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictSchema

type IssueStatus = Literal["open", "processing", "resolved", "rejected", "closed"]
type IssueAction = Literal["start_processing", "resolve", "reject", "close"]


class SubmitProgressReportRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    node_id: UUID | None = None
    progress_percent: int = Field(ge=0, le=100)
    report_content: str = Field(min_length=1)
    stage_result: str | None = None
    difficulty: str | None = None
    resource_request: str | None = None
    actual_hours: Decimal | None = Field(default=None, ge=0)
    corrects_report_id: UUID | None = None


class ProgressReportResponse(StrictSchema):
    progress_report_id: UUID
    task_id: UUID
    node_id: UUID | None
    reporter_employee_no: str
    progress_percent: int
    report_content: str
    stage_result: str | None
    difficulty: str | None
    resource_request: str | None
    actual_hours: Decimal | None
    corrects_report_id: UUID | None
    report_period_start: datetime | None
    report_period_end: datetime | None
    task_version: int
    operation_source: str
    created_at: datetime


class PaginatedProgressReportResponse(StrictSchema):
    items: list[ProgressReportResponse]
    limit: int
    offset: int
    total: int


class CreateTaskIssueRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    node_id: UUID | None = None
    source_progress_report_id: UUID | None = None
    issue_type: Literal["blocker", "resource_request", "collaboration_support", "risk"]
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requested_resource: str | None = None
    severity: Literal["low", "medium", "high", "critical"]
    owner_employee_no: str = Field(min_length=1)


class TaskIssueActionRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    reason: str | None = None


class TaskIssueResponse(StrictSchema):
    issue_id: UUID
    task_id: UUID
    node_id: UUID | None
    source_progress_report_id: UUID | None
    reported_by_employee_no: str
    issue_type: str
    title: str
    description: str
    requested_resource: str | None
    severity: str
    status: IssueStatus
    owner_employee_no: str
    resolution_note: str | None
    resolved_by_employee_no: str | None
    rejected_by_employee_no: str | None
    closed_by_employee_no: str | None
    created_at: datetime
    processing_started_at: datetime | None
    resolved_at: datetime | None
    rejected_at: datetime | None
    closed_at: datetime | None
    allowed_actions: list[IssueAction]


class PaginatedTaskIssueResponse(StrictSchema):
    items: list[TaskIssueResponse]
    limit: int
    offset: int
    total: int


class ReportDueItemResponse(StrictSchema):
    task_id: UUID
    task_no: str | None
    task_name: str
    task_version: int
    report_period_start: datetime
    report_period_end: datetime
    overdue_seconds: int


class ReportDueResponse(StrictSchema):
    items: list[ReportDueItemResponse]
    total: int
    calculated_at: datetime
