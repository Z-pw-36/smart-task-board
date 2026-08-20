from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import TaskIssue
from app.repositories import (
    ProgressReportRepository,
    TaskIssueRepository,
    TaskRepository,
)
from app.services.clock import Clock, utc_now
from app.services.errors import (
    BusinessValidationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.services.progress_report import task_report_period
from app.services.task_issue import issue_allowed_actions
from app.services.task_workflow import _aware_utc


class ProgressIssueQueryService:
    """Read progress reports, issues, and reporting obligations safely."""

    def __init__(self, session: Session, clock: Clock = utc_now) -> None:
        self._session = session
        self._clock = clock
        self._tasks = TaskRepository(session)
        self._reports = ProgressReportRepository(session)
        self._issues = TaskIssueRepository(session)

    def list_reports(
        self,
        task_id: UUID,
        actor_employee_no: str,
        *,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        self._require_task_access(task_id, actor_employee_no)
        self._validate_pagination(limit, offset)
        return {
            "items": [
                self._report_dict(item)
                for item in self._reports.list_by_task_id(
                    task_id,
                    limit=limit,
                    offset=offset,
                )
            ],
            "limit": limit,
            "offset": offset,
            "total": self._reports.count_by_task_id(task_id),
        }

    def get_report(
        self,
        task_id: UUID,
        progress_report_id: UUID,
        actor_employee_no: str,
    ) -> dict[str, Any]:
        self._require_task_access(task_id, actor_employee_no)
        report = self._reports.get_by_task_and_id(task_id, progress_report_id)
        if report is None:
            raise EntityNotFoundError("progress report was not found")
        return self._report_dict(report)

    def list_issues(
        self,
        task_id: UUID,
        actor_employee_no: str,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        self._require_task_access(task_id, actor_employee_no)
        self._validate_pagination(limit, offset)
        items = self._issues.list_by_task_id(
            task_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [self._issue_dict(item, actor_employee_no) for item in items],
            "limit": limit,
            "offset": offset,
            "total": self._issues.count_by_task_id(task_id, status=status),
        }

    def get_issue(
        self,
        task_id: UUID,
        issue_id: UUID,
        actor_employee_no: str,
    ) -> dict[str, Any]:
        self._require_task_access(task_id, actor_employee_no)
        issue = self._issues.get_by_id(issue_id)
        if issue is None or issue.task_id != task_id:
            raise EntityNotFoundError("task issue was not found")
        return self._issue_dict(issue, actor_employee_no)

    def list_report_due(self, actor_employee_no: str) -> dict[str, Any]:
        now = _aware_utc(self._clock(), "clock")
        items: list[dict[str, Any]] = []
        for task in self._tasks.list_report_due_candidates(actor_employee_no):
            period_start, period_end = task_report_period(
                task.report_cycle,
                task.accepted_at,
                now,
            )
            if period_end is None or period_end > now:
                continue
            if self._reports.has_root_task_report_for_period(
                task.task_id,
                period_end,
            ):
                continue
            items.append(
                {
                    "task_id": task.task_id,
                    "task_no": task.task_no,
                    "task_name": task.task_name,
                    "task_version": task.task_version,
                    "report_period_start": period_start,
                    "report_period_end": period_end,
                    "overdue_seconds": int((now - period_end).total_seconds()),
                }
            )
        items.sort(key=lambda item: (item["report_period_end"], str(item["task_id"])))
        return {"items": items, "total": len(items), "calculated_at": now}

    def _require_task_access(self, task_id: UUID, actor_employee_no: str) -> None:
        if self._tasks.get_by_id(task_id) is None:
            raise EntityNotFoundError("task was not found")
        if not self._tasks.is_related(task_id, actor_employee_no):
            raise PermissionDeniedError("actor cannot read this task")

    @staticmethod
    def _validate_pagination(limit: int, offset: int) -> None:
        if not 1 <= limit <= 100:
            raise BusinessValidationError("limit must be between 1 and 100")
        if offset < 0:
            raise BusinessValidationError("offset must not be negative")

    @staticmethod
    def _report_dict(report) -> dict[str, Any]:
        return {
            "progress_report_id": report.progress_report_id,
            "task_id": report.task_id,
            "node_id": report.node_id,
            "reporter_employee_no": report.reporter_employee_no,
            "progress_percent": report.progress_percent,
            "report_content": report.report_content,
            "stage_result": report.stage_result,
            "difficulty": report.difficulty,
            "resource_request": report.resource_request,
            "actual_hours": report.actual_hours,
            "corrects_report_id": report.corrects_report_id,
            "report_period_start": report.report_period_start,
            "report_period_end": report.report_period_end,
            "task_version": report.task_version,
            "operation_source": report.operation_source,
            "created_at": report.created_at,
        }

    @classmethod
    def _issue_dict(cls, issue: TaskIssue, actor_employee_no: str) -> dict[str, Any]:
        return {
            "issue_id": issue.issue_id,
            "task_id": issue.task_id,
            "node_id": issue.node_id,
            "source_progress_report_id": issue.source_progress_report_id,
            "reported_by_employee_no": issue.reported_by_employee_no,
            "issue_type": issue.issue_type,
            "title": issue.title,
            "description": issue.description,
            "requested_resource": issue.requested_resource,
            "severity": issue.severity,
            "status": issue.status,
            "owner_employee_no": issue.owner_employee_no,
            "resolution_note": issue.resolution_note,
            "resolved_by_employee_no": issue.resolved_by_employee_no,
            "rejected_by_employee_no": issue.rejected_by_employee_no,
            "closed_by_employee_no": issue.closed_by_employee_no,
            "created_at": issue.created_at,
            "processing_started_at": issue.processing_started_at,
            "resolved_at": issue.resolved_at,
            "rejected_at": issue.rejected_at,
            "closed_at": issue.closed_at,
            "allowed_actions": issue_allowed_actions(issue, actor_employee_no),
        }
