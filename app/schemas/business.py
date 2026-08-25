from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.schemas.common import DecimalString, NonNegativeDecimalString, StrictSchema
from app.schemas.task_node import _require_aware

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SystemParameterResponse(StrictSchema):
    parameter_id: UUID
    param_key: str
    param_name: str
    param_value: str
    param_type: Literal["number", "string", "boolean", "json"]
    module: str
    description: str | None
    is_active: bool
    updated_by_employee_no: str | None
    updated_at: datetime


class SystemParameterUpdateRequest(StrictSchema):
    param_value: NonBlankString
    param_type: Literal["number", "string", "boolean", "json"] = "number"
    param_name: str | None = None
    module: NonBlankString = "general"
    description: str | None = None
    is_active: bool = True


class EmployeeProfileUpsertRequest(StrictSchema):
    responsibility_text: str | None = None
    skill_tags: list[str] = Field(default_factory=list)
    daily_capacity_hours: NonNegativeDecimalString = Decimal("8")
    standard_task_count: int = Field(default=5, ge=1)
    standard_task_weight: int = Field(default=3, ge=1, le=5)
    emergency_tolerance_count: int = Field(default=3, ge=0)
    availability_status: Literal["available", "busy", "unavailable", "disabled"] = "available"


class EmployeeProfileResponse(EmployeeProfileUpsertRequest):
    employee_no: str
    updated_at: datetime


class RecommendationRequest(StrictSchema):
    task_description: NonBlankString
    required_skill_tags: list[str] = Field(default_factory=list)
    department_id: UUID | None = None
    limit: int = Field(default=5, ge=1, le=20)


class RecommendationResponse(StrictSchema):
    employee_no: str
    name: str
    score: DecimalString
    reasons: list[str]


class AuthorizedScopeCreateRequest(StrictSchema):
    employee_no: NonBlankString
    scope_type: Literal["department", "user", "role", "all_demo_data"]
    scope_id: str | None = None
    permission_type: Literal["view", "manage", "export"] = "view"
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    status: Literal["active", "expired", "disabled"] = "active"

    _validate_from = field_validator("valid_from")(_require_aware)
    _validate_to = field_validator("valid_to")(_require_aware)

    @model_validator(mode="after")
    def validate_window(self) -> AuthorizedScopeCreateRequest:
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to < self.valid_from
        ):
            raise ValueError("valid_to must not precede valid_from")
        if self.scope_type != "all_demo_data" and not self.scope_id:
            raise ValueError("scope_id is required for this scope_type")
        return self


class AuthorizedScopeResponse(StrictSchema):
    authorized_scope_id: UUID
    employee_no: str
    scope_type: str
    scope_id: str | None
    permission_type: str
    valid_from: datetime | None
    valid_to: datetime | None
    status: str
    created_by_employee_no: str | None
    created_at: datetime


class TaskInputCreateRequest(StrictSchema):
    input_id: UUID | None = None
    input_type: Literal["text", "voice", "wecom_text"] = "text"
    raw_text: str | None = None
    voice_file_url: str | None = None
    source_channel: Literal["web", "api", "wecom"] = "api"

    @model_validator(mode="after")
    def validate_content(self) -> TaskInputCreateRequest:
        if self.input_type == "voice":
            if not self.voice_file_url:
                raise ValueError("voice_file_url is required for voice input")
        elif not self.raw_text or not self.raw_text.strip():
            raise ValueError("raw_text is required for text input")
        return self


class TaskClarificationRequest(StrictSchema):
    answers: dict[str, Any] = Field(min_length=1)


class TaskIntakeResponse(StrictSchema):
    input_id: UUID
    input_type: str
    raw_text: str | None
    asr_text: str | None
    source_channel: str
    submitted_by_employee_no: str
    submitted_at: datetime
    extraction_id: UUID
    extracted_json: dict[str, Any]
    missing_fields: list[str]
    low_confidence_fields: list[str]
    confirm_questions: list[str]
    confidence_score: DecimalString | None


class ConfirmExtractionTaskRequest(StrictSchema):
    task_id: UUID | None = None
    extraction_id: UUID
    corrections: dict[str, Any] = Field(default_factory=dict)


class PerformanceMetricCreateRequest(StrictSchema):
    metric_type: NonBlankString
    metric_name: NonBlankString
    period: str | None = None
    business_unit: str | None = None
    sequence_no: int | None = None
    dimension: str | None = None
    definition_formula: str | None = None
    weight: NonNegativeDecimalString | None = None
    target_value: str | None = None
    deliverable: str | None = None
    data_source: str | None = None
    status: Literal["active", "inactive"] = "active"


class PerformanceMetricResponse(PerformanceMetricCreateRequest):
    metric_id: UUID
    created_at: datetime
    updated_at: datetime


class PerformanceMatchResponse(StrictSchema):
    performance_match_id: UUID
    task_id: UUID
    metric_id: UUID
    type_score: DecimalString
    business_unit_score: DecimalString
    metric_name_score: DecimalString
    definition_formula_score: DecimalString
    deliverable_score: DecimalString
    total_score: DecimalString
    match_level: Literal["strong", "weak", "no_clear_relation"]
    match_reason: str | None
    is_confirmed: bool
    confirmed_by_employee_no: str | None
    confirmed_at: datetime | None
    algorithm_version: str
    created_at: datetime
    updated_at: datetime


class WorkloadCalculationRequest(StrictSchema):
    period_start: datetime
    period_end: datetime

    _validate_start = field_validator("period_start")(_require_aware)
    _validate_end = field_validator("period_end")(_require_aware)

    @model_validator(mode="after")
    def validate_period(self) -> WorkloadCalculationRequest:
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        return self


class WorkloadSnapshotResponse(StrictSchema):
    workload_snapshot_id: UUID
    employee_no: str
    period_start: datetime
    period_end: datetime
    remaining_hours_sum: DecimalString
    available_hours: DecimalString
    active_task_count: int
    active_task_weight_sum: DecimalString
    urgent_task_count: int
    blocked_task_count: int
    overdue_task_count: int
    hours_pressure: DecimalString
    weight_pressure: DecimalString
    count_pressure: DecimalString
    urgent_pressure: DecimalString
    blocked_overdue_pressure: DecimalString
    workload_score: DecimalString
    workload_level: str
    parameter_snapshot: dict[str, Any]
    calculated_at: datetime


class PriorityScoreResponse(StrictSchema):
    priority_score_id: UUID
    task_id: UUID
    task_weight_score: DecimalString
    performance_match_score: DecimalString
    report_to_level_score: DecimalString
    importance_score: DecimalString
    time_pressure_score: DecimalString
    overdue_pressure_score: DecimalString
    urgent_pressure_score: DecimalString
    urgency_score: DecimalString
    priority_quadrant: str
    remaining_hours: DecimalString | None
    sort_rank: int | None
    task_created_at_snapshot: datetime
    explanation: dict[str, Any]
    calculated_at: datetime


class ConflictResponse(StrictSchema):
    conflict_id: UUID
    conflict_type: str
    employee_no: str
    task_id: UUID
    related_task_id: UUID | None
    node_id: UUID | None
    dedupe_key: str
    severity: str
    description: str
    suggestion: str | None
    status: str
    resolved_by_employee_no: str | None
    resolution_note: str | None
    detected_at: datetime
    resolved_at: datetime | None


class ResolveConflictRequest(StrictSchema):
    resolution_note: NonBlankString


class ReminderRuleResponse(StrictSchema):
    reminder_rule_id: UUID
    task_id: UUID | None
    node_id: UUID | None
    issue_id: UUID | None
    reminder_type: str
    recipient_employee_no: str
    trigger_time: datetime | None
    next_trigger_at: datetime | None
    repeat_rule: str | None
    dedupe_key: str
    is_active: bool
    last_triggered_at: datetime | None
    created_at: datetime


class NotificationResponse(StrictSchema):
    notification_id: UUID
    reminder_rule_id: UUID | None
    task_id: UUID | None
    issue_id: UUID | None
    recipient_employee_no: str
    channel: str
    title: str
    content: str
    send_status: str
    wecom_message_id: str | None
    fail_reason: str | None
    retry_count: int
    retry_next_at: datetime | None
    sent_at: datetime | None
    read_at: datetime | None
    dedupe_key: str
    created_at: datetime


class ArchiveCreateRequest(StrictSchema):
    summary: str | None = None
    search_keywords: list[str] = Field(default_factory=list)
    review_result: str | None = None
    risk_points: list[str] = Field(default_factory=list)


class TaskArchiveResponse(StrictSchema):
    archive_id: UUID
    task_id: UUID
    archive_snapshot: dict[str, Any]
    source_status_snapshot: str
    summary: str | None
    search_keywords: list[str]
    review_result: str | None
    risk_points: list[str]
    reusable_template: dict[str, Any] | None
    actual_hours_total: DecimalString | None
    archived_by_employee_no: str
    archived_at: datetime


class ArchiveSearchResponse(StrictSchema):
    items: list[TaskArchiveResponse]
    limit: int
    offset: int
    total: int


class OperationLogResponse(StrictSchema):
    operation_log_id: UUID
    request_id: str | None
    operator_employee_no: str | None
    action: str
    object_type: str
    object_id: str
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    result: str
    error_message: str | None
    created_at: datetime


class OperationLogPageResponse(StrictSchema):
    items: list[OperationLogResponse]
    limit: int
    offset: int
    total: int


class ReuseArchiveRequest(StrictSchema):
    task_id: UUID | None = None
    task_name: NonBlankString | None = None
    main_assignee_employee_no: str | None = None
    deadline: datetime | None = None

    _validate_deadline = field_validator("deadline")(_require_aware)
