from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai.providers import OpenAICompatibleTaskAgentProvider
from app.api.errors import AuthenticationRequiredError
from app.core.config import get_settings
from app.core.security import InvalidPrototypeTokenError, decode_access_token
from app.db.session import SessionLocal, get_db
from app.db.unit_of_work import UnitOfWork
from app.services.authentication import AuthenticationService
from app.services.business_capabilities import (
    ArchiveReuseService,
    AuditQueryService,
    PerformanceMetricService,
    PermissionScopeService,
    PlanningAnalyticsService,
    ReminderNotificationService,
    SystemParameterService,
    TaskIntakeService,
)
from app.services.progress_issue_query import ProgressIssueQueryService
from app.services.progress_report import ProgressReportService
from app.services.task_issue import TaskIssueService
from app.services.task_node_workflow import TaskNodeWorkflowService
from app.services.task_query import TaskQueryService
from app.services.task_workflow import TaskWorkflowService

UowFactory = Callable[[], UnitOfWork]
prototype_bearer = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description="Short-lived JWT for isolated prototype use only.",
)


def get_current_employee_no(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(prototype_bearer),
    ] = None,
) -> str:
    settings = get_settings()
    if "authorization" in request.headers:
        if credentials is None or credentials.scheme.casefold() != "bearer":
            raise AuthenticationRequiredError
        token = credentials.credentials.strip()
        if not token:
            raise AuthenticationRequiredError
        try:
            return decode_access_token(token, settings)
        except InvalidPrototypeTokenError as exc:
            raise AuthenticationRequiredError from exc

    if settings.allow_test_employee_header:
        employee_no = request.headers.get("X-Employee-No")
        if employee_no is not None and employee_no.strip():
            return employee_no.strip()
    raise AuthenticationRequiredError


def get_uow_factory() -> UowFactory:
    return lambda: UnitOfWork(SessionLocal)


def get_task_workflow_service(
    uow_factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TaskWorkflowService:
    return TaskWorkflowService(uow_factory)


def get_task_node_workflow_service(
    uow_factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TaskNodeWorkflowService:
    return TaskNodeWorkflowService(uow_factory)


def get_progress_report_service(
    uow_factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> ProgressReportService:
    return ProgressReportService(uow_factory)


def get_task_issue_service(
    uow_factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TaskIssueService:
    return TaskIssueService(uow_factory)


def get_progress_issue_query_service(
    session: Annotated[Session, Depends(get_db)],
) -> ProgressIssueQueryService:
    return ProgressIssueQueryService(session)


def get_task_query_service(
    session: Annotated[Session, Depends(get_db)],
) -> TaskQueryService:
    return TaskQueryService(session)


def get_identity_service(
    session: Annotated[Session, Depends(get_db)],
):
    from app.services.identity import IdentityService

    return IdentityService(session)


def get_authentication_service(
    session: Annotated[Session, Depends(get_db)],
) -> AuthenticationService:
    return AuthenticationService(session, get_settings())


def get_task_board_query_service(
    session: Annotated[Session, Depends(get_db)],
):
    from app.services.task_board_query import TaskBoardQueryService

    return TaskBoardQueryService(session)


def get_system_parameter_service(
    session: Annotated[Session, Depends(get_db)],
) -> SystemParameterService:
    return SystemParameterService(session)


def get_permission_scope_service(
    session: Annotated[Session, Depends(get_db)],
) -> PermissionScopeService:
    return PermissionScopeService(session)


def get_intake_service(
    session: Annotated[Session, Depends(get_db)],
    uow_factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TaskIntakeService:
    settings = get_settings()
    if settings.ai_provider == "openai_compatible":
        provider = OpenAICompatibleTaskAgentProvider.from_settings(settings)
        return TaskIntakeService(
            session,
            uow_factory,
            extraction_provider=provider,
            decomposition_provider=provider,
            agent_timezone=settings.app_timezone,
        )
    return TaskIntakeService(session, uow_factory, agent_timezone=settings.app_timezone)


def get_performance_metric_service(
    session: Annotated[Session, Depends(get_db)],
) -> PerformanceMetricService:
    return PerformanceMetricService(session)


def get_planning_analytics_service(
    session: Annotated[Session, Depends(get_db)],
) -> PlanningAnalyticsService:
    return PlanningAnalyticsService(session)


def get_notification_service(
    session: Annotated[Session, Depends(get_db)],
) -> ReminderNotificationService:
    return ReminderNotificationService(session)


def get_archive_reuse_service(
    session: Annotated[Session, Depends(get_db)],
    uow_factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> ArchiveReuseService:
    return ArchiveReuseService(session, uow_factory)


def get_audit_query_service(
    session: Annotated[Session, Depends(get_db)],
) -> AuditQueryService:
    return AuditQueryService(session)
