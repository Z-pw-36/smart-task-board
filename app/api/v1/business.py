from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    get_archive_reuse_service,
    get_audit_query_service,
    get_current_employee_no,
    get_intake_service,
    get_notification_service,
    get_performance_metric_service,
    get_permission_scope_service,
    get_planning_analytics_service,
    get_system_parameter_service,
)
from app.models import EmployeeProfile
from app.schemas.business import (
    ArchiveCreateRequest,
    ArchiveSearchResponse,
    AuthorizedScopeCreateRequest,
    AuthorizedScopeResponse,
    ConfirmExtractionTaskRequest,
    ConflictResponse,
    EmployeeProfileResponse,
    EmployeeProfileUpsertRequest,
    NotificationResponse,
    OperationLogPageResponse,
    PerformanceMatchResponse,
    PerformanceMetricCreateRequest,
    PerformanceMetricResponse,
    PriorityScoreResponse,
    RecommendationRequest,
    RecommendationResponse,
    ReminderRuleResponse,
    ResolveConflictRequest,
    ReuseArchiveRequest,
    SystemParameterResponse,
    SystemParameterUpdateRequest,
    TaskArchiveResponse,
    TaskClarificationRequest,
    TaskExtractionResponse,
    TaskInputCreateRequest,
    TaskIntakeResponse,
    WorkloadCalculationRequest,
    WorkloadSnapshotResponse,
)
from app.schemas.task import TaskActionResponse
from app.services.business_capabilities import (
    ArchiveReuseService,
    AuditQueryService,
    IntakeResult,
    PerformanceMetricService,
    PermissionScopeService,
    PlanningAnalyticsService,
    ReminderNotificationService,
    SystemParameterService,
)

router = APIRouter(tags=["business-capabilities"])

Actor = Annotated[str, Depends(get_current_employee_no)]
ParameterService = Annotated[SystemParameterService, Depends(get_system_parameter_service)]
PermissionService = Annotated[PermissionScopeService, Depends(get_permission_scope_service)]
IntakeService = Annotated[Any, Depends(get_intake_service)]
MetricService = Annotated[PerformanceMetricService, Depends(get_performance_metric_service)]
PlanningService = Annotated[PlanningAnalyticsService, Depends(get_planning_analytics_service)]
NotificationService = Annotated[ReminderNotificationService, Depends(get_notification_service)]
ArchiveService = Annotated[ArchiveReuseService, Depends(get_archive_reuse_service)]
AuditService = Annotated[AuditQueryService, Depends(get_audit_query_service)]


def _intake_response(result: IntakeResult) -> TaskIntakeResponse:
    task_input = result.task_input
    extraction = result.extraction
    return TaskIntakeResponse(
        input_id=task_input.input_id,
        input_type=task_input.input_type,
        raw_text=task_input.raw_text,
        asr_text=task_input.asr_text,
        source_channel=task_input.source_channel,
        submitted_by_employee_no=task_input.submitted_by_employee_no,
        submitted_at=task_input.submitted_at,
        extraction_id=extraction.extraction_id,
        extracted_json=extraction.extracted_json,
        missing_fields=extraction.missing_fields,
        low_confidence_fields=extraction.low_confidence_fields,
        confirm_questions=extraction.confirm_questions,
        confidence_score=extraction.confidence_score,
    )


def _extraction_response(result: IntakeResult) -> TaskExtractionResponse:
    return TaskExtractionResponse.model_validate(_intake_response(result))


@router.get(
    "/system-parameters",
    response_model=list[SystemParameterResponse],
    summary="List active and default business parameters",
)
def list_system_parameters(
    _actor: Actor,
    service: ParameterService,
) -> list[Any]:
    return service.list_parameters()


@router.put(
    "/system-parameters/{param_key}",
    response_model=SystemParameterResponse,
    summary="Create or update a business parameter",
)
def upsert_system_parameter(
    param_key: str,
    request: SystemParameterUpdateRequest,
    actor: Actor,
    service: ParameterService,
) -> Any:
    return service.upsert_parameter(
        actor,
        param_key,
        value=request.param_value,
        param_type=request.param_type,
        module=request.module,
        name=request.param_name,
        description=request.description,
        is_active=request.is_active,
    )


@router.put(
    "/organization/employee-profiles/{employee_no}",
    response_model=EmployeeProfileResponse,
    summary="Create or update an employee capability profile",
)
def upsert_employee_profile(
    employee_no: str,
    request: EmployeeProfileUpsertRequest,
    actor: Actor,
    service: PermissionService,
) -> Any:
    service._require_admin(actor)
    existing = service.session.get(EmployeeProfile, employee_no)
    now = service.clock()
    if existing is None:
        existing = EmployeeProfile(employee_no=employee_no, updated_at=now)
        service.session.add(existing)
    existing.responsibility_text = request.responsibility_text
    existing.skill_tags = request.skill_tags
    existing.daily_capacity_hours = request.daily_capacity_hours
    existing.standard_task_count = request.standard_task_count
    existing.standard_task_weight = request.standard_task_weight
    existing.emergency_tolerance_count = request.emergency_tolerance_count
    existing.availability_status = request.availability_status
    existing.updated_at = now
    service.session.commit()
    return existing


@router.post(
    "/organization/recommendations/assignees",
    response_model=list[RecommendationResponse],
    summary="Recommend assignees without bypassing human confirmation",
)
def recommend_assignees(
    request: RecommendationRequest,
    actor: Actor,
    service: PermissionService,
) -> list[dict[str, object]]:
    return service.recommend_assignees(
        actor,
        task_description=request.task_description,
        required_skill_tags=request.required_skill_tags,
        department_id=request.department_id,
        limit=request.limit,
    )


@router.post(
    "/permissions/scopes",
    response_model=AuthorizedScopeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant an explicit user authorization scope",
)
def grant_authorized_scope(
    request: AuthorizedScopeCreateRequest,
    actor: Actor,
    service: PermissionService,
) -> Any:
    return service.grant_scope(
        actor,
        employee_no=request.employee_no,
        scope_type=request.scope_type,
        scope_id=request.scope_id,
        permission_type=request.permission_type,
        valid_from=request.valid_from,
        valid_to=request.valid_to,
        status=request.status,
    )


@router.get(
    "/permissions/scopes",
    response_model=list[AuthorizedScopeResponse],
    summary="List authorization scopes for the current or selected user",
)
def list_authorized_scopes(
    actor: Actor,
    service: PermissionService,
    employee_no: str | None = None,
) -> list[Any]:
    return service.list_scopes(actor, employee_no)


@router.post(
    "/task-inputs",
    response_model=TaskIntakeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit text, voice, or simulated WeCom task input",
)
def submit_task_input(
    request: TaskInputCreateRequest,
    actor: Actor,
    service: IntakeService,
) -> TaskIntakeResponse:
    return _intake_response(
        service.submit_input(
            actor,
            input_id=request.input_id,
            input_type=request.input_type,
            raw_text=request.raw_text,
            voice_file_url=request.voice_file_url,
            source_channel=request.source_channel,
        )
    )


@router.post(
    "/task-inputs/{input_id}/extract",
    response_model=TaskExtractionResponse,
    summary="Retry field extraction for an existing task input",
)
def retry_task_input_extraction(
    input_id: UUID,
    actor: Actor,
    service: IntakeService,
) -> TaskExtractionResponse:
    return _extraction_response(service.retry_extraction(actor, input_id))


@router.get(
    "/task-inputs/{input_id}/extraction",
    response_model=TaskExtractionResponse,
    summary="Get the latest field extraction result for a task input",
)
def get_task_input_extraction(
    input_id: UUID,
    actor: Actor,
    service: IntakeService,
) -> TaskExtractionResponse:
    return _extraction_response(service.get_latest_extraction(actor, input_id))


@router.post(
    "/task-inputs/{input_id}/clarifications",
    response_model=TaskIntakeResponse,
    summary="Add user clarification and create a new extraction round",
)
def clarify_task_input(
    input_id: UUID,
    request: TaskClarificationRequest,
    actor: Actor,
    service: IntakeService,
) -> TaskIntakeResponse:
    return _intake_response(service.clarify(actor, input_id, request.answers))


@router.post(
    "/task-inputs/{input_id}/confirm-task",
    response_model=TaskActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm an extraction and create an idempotent task draft",
)
def confirm_task_input(
    input_id: UUID,
    request: ConfirmExtractionTaskRequest,
    actor: Actor,
    service: IntakeService,
) -> TaskActionResponse:
    result = service.create_draft_from_extraction(
        actor,
        extraction_id=request.extraction_id,
        corrections={"input_id": str(input_id), **request.corrections},
        task_id=request.task_id,
    )
    return TaskActionResponse.model_validate(result)


@router.post(
    "/performance-metrics",
    response_model=PerformanceMetricResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a performance metric",
)
def create_performance_metric(
    request: PerformanceMetricCreateRequest,
    actor: Actor,
    service: MetricService,
) -> Any:
    return service.create_metric(actor, request.model_dump())


@router.get(
    "/performance-metrics",
    response_model=list[PerformanceMetricResponse],
    summary="List performance metrics",
)
def list_performance_metrics(_actor: Actor, service: MetricService) -> list[Any]:
    return service.list_metrics()


@router.post(
    "/tasks/{task_id}/performance-matches/suggest",
    response_model=list[PerformanceMatchResponse],
    summary="Suggest KPI matches for a task",
)
def suggest_performance_matches(
    task_id: UUID,
    actor: Actor,
    service: MetricService,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[Any]:
    return service.suggest_matches(actor, task_id, limit)


@router.post(
    "/tasks/{task_id}/performance-matches/{performance_match_id}/confirm",
    response_model=PerformanceMatchResponse,
    summary="Confirm a suggested KPI match",
)
def confirm_performance_match(
    task_id: UUID,
    performance_match_id: UUID,
    actor: Actor,
    service: MetricService,
) -> Any:
    return service.confirm_match(actor, task_id, performance_match_id)


@router.post(
    "/analytics/workload/{employee_no}",
    response_model=WorkloadSnapshotResponse,
    summary="Calculate and persist an employee workload snapshot",
)
def calculate_workload(
    employee_no: str,
    request: WorkloadCalculationRequest,
    actor: Actor,
    service: PlanningService,
) -> Any:
    return service.calculate_workload(actor, employee_no, request.period_start, request.period_end)


@router.post(
    "/analytics/priorities",
    response_model=list[PriorityScoreResponse],
    summary="Calculate and persist visible task priority snapshots",
)
def calculate_priorities(actor: Actor, service: PlanningService) -> list[Any]:
    return service.calculate_priorities(actor)


@router.post(
    "/analytics/conflicts/detect",
    response_model=list[ConflictResponse],
    summary="Detect and deduplicate active task conflicts",
)
def detect_conflicts(
    actor: Actor,
    service: PlanningService,
    employee_no: str | None = None,
) -> list[Any]:
    return service.detect_conflicts(actor, employee_no)


@router.post(
    "/conflicts/{conflict_id}/actions/acknowledge",
    response_model=ConflictResponse,
    summary="Acknowledge an open conflict",
)
def acknowledge_conflict(
    conflict_id: UUID,
    request: ResolveConflictRequest,
    actor: Actor,
    service: PlanningService,
) -> Any:
    return service.resolve_conflict(
        actor,
        conflict_id,
        resolution_note=request.resolution_note,
        status="acknowledged",
    )


@router.post(
    "/conflicts/{conflict_id}/actions/resolve",
    response_model=ConflictResponse,
    summary="Resolve an open conflict",
)
def resolve_conflict(
    conflict_id: UUID,
    request: ResolveConflictRequest,
    actor: Actor,
    service: PlanningService,
) -> Any:
    return service.resolve_conflict(actor, conflict_id, resolution_note=request.resolution_note)


@router.post(
    "/conflicts/{conflict_id}/actions/ignore",
    response_model=ConflictResponse,
    summary="Ignore an open conflict",
)
def ignore_conflict(
    conflict_id: UUID,
    request: ResolveConflictRequest,
    actor: Actor,
    service: PlanningService,
) -> Any:
    return service.resolve_conflict(
        actor,
        conflict_id,
        resolution_note=request.resolution_note,
        status="ignored",
    )


@router.post(
    "/reminders/scan",
    response_model=list[ReminderRuleResponse],
    summary="Scan active tasks and persist reminder rules",
)
def scan_reminders(actor: Actor, service: NotificationService) -> list[Any]:
    return service.scan_reminders(actor)


@router.post(
    "/notifications/send-pending",
    response_model=list[NotificationResponse],
    summary="Create delivery attempts for due notifications with finite retry",
)
def send_pending_notifications(actor: Actor, service: NotificationService) -> list[Any]:
    service.create_due_notifications(actor)
    return service.send_pending(actor)


@router.get(
    "/notifications",
    response_model=list[NotificationResponse],
    summary="List current user's notifications",
)
def list_notifications(
    actor: Actor,
    service: NotificationService,
    unread_only: bool = False,
) -> list[Any]:
    return service.list_notifications(actor, unread_only=unread_only)


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark a notification as read",
)
def mark_notification_read(
    notification_id: UUID,
    actor: Actor,
    service: NotificationService,
) -> Any:
    return service.mark_read(actor, notification_id)


@router.post(
    "/tasks/{task_id}/archive-snapshot",
    response_model=TaskArchiveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persist a reusable archive snapshot for a task",
)
def archive_task_snapshot(
    task_id: UUID,
    request: ArchiveCreateRequest,
    actor: Actor,
    service: ArchiveService,
) -> Any:
    return service.archive_task(
        actor,
        task_id,
        summary=request.summary,
        search_keywords=request.search_keywords,
        review_result=request.review_result,
        risk_points=request.risk_points,
    )


@router.get(
    "/archives/search",
    response_model=ArchiveSearchResponse,
    summary="Search archived task snapshots",
)
def search_archives(
    actor: Actor,
    service: ArchiveService,
    keyword: str | None = None,
    creator: str | None = None,
    assignee: str | None = None,
    department_id: UUID | None = None,
    archived_from: datetime | None = None,
    archived_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    return service.search(
        actor,
        keyword=keyword,
        creator=creator,
        assignee=assignee,
        department_id=department_id,
        archived_from=archived_from,
        archived_to=archived_to,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/tasks/{task_id}/similar-archives",
    response_model=list[TaskArchiveResponse],
    summary="Find similar archived tasks with deterministic local matching",
)
def similar_archives(
    task_id: UUID,
    actor: Actor,
    service: ArchiveService,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> list[Any]:
    return service.similar(actor, task_id, limit=limit)


@router.post(
    "/archives/{archive_id}/reuse",
    response_model=TaskActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reuse an archived task as a new draft",
)
def reuse_archive(
    archive_id: UUID,
    request: ReuseArchiveRequest,
    actor: Actor,
    service: ArchiveService,
) -> TaskActionResponse:
    return TaskActionResponse.model_validate(
        service.reuse_archive(
            actor,
            archive_id,
            task_id=request.task_id,
            task_name=request.task_name,
            main_assignee_employee_no=request.main_assignee_employee_no,
            deadline=request.deadline,
        )
    )


@router.get(
    "/operation-logs",
    response_model=OperationLogPageResponse,
    summary="List operation audit logs",
)
def list_operation_logs(
    actor: Actor,
    service: AuditService,
    object_type: str | None = None,
    object_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    return service.list_logs(
        actor,
        object_type=object_type,
        object_id=object_id,
        limit=limit,
        offset=offset,
    )
