from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    get_current_employee_no,
    get_progress_issue_query_service,
    get_progress_report_service,
    get_task_issue_service,
)
from app.schemas import ErrorResponse
from app.schemas.progress_issue import (
    CreateTaskIssueRequest,
    IssueStatus,
    PaginatedProgressReportResponse,
    PaginatedTaskIssueResponse,
    ProgressReportResponse,
    ReportDueResponse,
    SubmitProgressReportRequest,
    TaskIssueActionRequest,
    TaskIssueResponse,
)
from app.services.commands import CreateTaskIssueCommand, SubmitProgressReportCommand
from app.services.progress_issue_query import ProgressIssueQueryService
from app.services.progress_report import ProgressReportService
from app.services.task_issue import TaskIssueService

router = APIRouter(prefix="/tasks", tags=["progress-and-issues"])
OPERATION_SOURCE = "rest_api"

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication required"},
    403: {"model": ErrorResponse, "description": "Permission denied"},
    404: {"model": ErrorResponse, "description": "Entity not found"},
    409: {"model": ErrorResponse, "description": "State, version, or resource conflict"},
    422: {"model": ErrorResponse, "description": "Request or business validation failed"},
}

Actor = Annotated[str, Depends(get_current_employee_no)]
ReportService = Annotated[ProgressReportService, Depends(get_progress_report_service)]
IssueService = Annotated[TaskIssueService, Depends(get_task_issue_service)]
QueryService = Annotated[
    ProgressIssueQueryService,
    Depends(get_progress_issue_query_service),
]


@router.get(
    "/report-due",
    response_model=ReportDueResponse,
    summary="List my currently due periodic task reports",
    responses=ERROR_RESPONSES,
)
def list_report_due(actor: Actor, query_service: QueryService) -> dict[str, Any]:
    return query_service.list_report_due(actor)


@router.post(
    "/{task_id}/progress-reports",
    response_model=ProgressReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an immutable task or node progress report",
    responses=ERROR_RESPONSES,
)
def submit_progress_report(
    task_id: UUID,
    request: SubmitProgressReportRequest,
    actor: Actor,
    service: ReportService,
) -> ProgressReportResponse:
    report = service.submit(
        SubmitProgressReportCommand(
            task_id=task_id,
            reporter_employee_no=actor,
            operation_source=OPERATION_SOURCE,
            **request.model_dump(),
        )
    )
    return ProgressReportResponse.model_validate(report)


@router.get(
    "/{task_id}/progress-reports",
    response_model=PaginatedProgressReportResponse,
    summary="List a task's progress report timeline",
    responses=ERROR_RESPONSES,
)
def list_progress_reports(
    task_id: UUID,
    actor: Actor,
    query_service: QueryService,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return query_service.list_reports(task_id, actor, limit=limit, offset=offset)


@router.get(
    "/{task_id}/progress-reports/{progress_report_id}",
    response_model=ProgressReportResponse,
    summary="Get one progress report",
    responses=ERROR_RESPONSES,
)
def get_progress_report(
    task_id: UUID,
    progress_report_id: UUID,
    actor: Actor,
    query_service: QueryService,
) -> dict[str, Any]:
    return query_service.get_report(task_id, progress_report_id, actor)


@router.post(
    "/{task_id}/issues",
    response_model=TaskIssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a task or node issue",
    responses=ERROR_RESPONSES,
)
def create_task_issue(
    task_id: UUID,
    request: CreateTaskIssueRequest,
    actor: Actor,
    service: IssueService,
) -> TaskIssueResponse:
    issue = service.create(
        CreateTaskIssueCommand(
            task_id=task_id,
            reported_by_employee_no=actor,
            operation_source=OPERATION_SOURCE,
            **request.model_dump(),
        )
    )
    payload = ProgressIssueQueryService._issue_dict(issue, actor)
    return TaskIssueResponse.model_validate(payload)


@router.get(
    "/{task_id}/issues",
    response_model=PaginatedTaskIssueResponse,
    summary="List task issues",
    responses=ERROR_RESPONSES,
)
def list_task_issues(
    task_id: UUID,
    actor: Actor,
    query_service: QueryService,
    issue_status: Annotated[IssueStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return query_service.list_issues(
        task_id,
        actor,
        status=issue_status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{task_id}/issues/{issue_id}",
    response_model=TaskIssueResponse,
    summary="Get one task issue",
    responses=ERROR_RESPONSES,
)
def get_task_issue(
    task_id: UUID,
    issue_id: UUID,
    actor: Actor,
    query_service: QueryService,
) -> dict[str, Any]:
    return query_service.get_issue(task_id, issue_id, actor)


def _transition(
    service: TaskIssueService,
    task_id: UUID,
    issue_id: UUID,
    actor: str,
    request: TaskIssueActionRequest,
    target_status: Literal["processing", "resolved", "rejected", "closed"],
) -> TaskIssueResponse:
    issue = service.transition(
        task_id,
        issue_id,
        actor,
        request.expected_task_version,
        OPERATION_SOURCE,
        target_status,
        request.reason,
    )
    return TaskIssueResponse.model_validate(
        ProgressIssueQueryService._issue_dict(issue, actor)
    )


@router.post(
    "/{task_id}/issues/{issue_id}/actions/start-processing",
    response_model=TaskIssueResponse,
    responses=ERROR_RESPONSES,
)
def start_processing(
    task_id: UUID,
    issue_id: UUID,
    request: TaskIssueActionRequest,
    actor: Actor,
    service: IssueService,
) -> TaskIssueResponse:
    return _transition(service, task_id, issue_id, actor, request, "processing")


@router.post(
    "/{task_id}/issues/{issue_id}/actions/resolve",
    response_model=TaskIssueResponse,
    responses=ERROR_RESPONSES,
)
def resolve_issue(
    task_id: UUID,
    issue_id: UUID,
    request: TaskIssueActionRequest,
    actor: Actor,
    service: IssueService,
) -> TaskIssueResponse:
    return _transition(service, task_id, issue_id, actor, request, "resolved")


@router.post(
    "/{task_id}/issues/{issue_id}/actions/reject",
    response_model=TaskIssueResponse,
    responses=ERROR_RESPONSES,
)
def reject_issue(
    task_id: UUID,
    issue_id: UUID,
    request: TaskIssueActionRequest,
    actor: Actor,
    service: IssueService,
) -> TaskIssueResponse:
    return _transition(service, task_id, issue_id, actor, request, "rejected")


@router.post(
    "/{task_id}/issues/{issue_id}/actions/close",
    response_model=TaskIssueResponse,
    responses=ERROR_RESPONSES,
)
def close_issue(
    task_id: UUID,
    issue_id: UUID,
    request: TaskIssueActionRequest,
    actor: Actor,
    service: IssueService,
) -> TaskIssueResponse:
    return _transition(service, task_id, issue_id, actor, request, "closed")
