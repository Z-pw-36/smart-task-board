from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.db.unit_of_work import UnitOfWork
from app.models import Task, TaskIssue, TaskNode
from app.services.clock import Clock, utc_now
from app.services.commands import CreateTaskIssueCommand
from app.services.errors import (
    BusinessValidationError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    PermissionDeniedError,
)
from app.services.task_workflow import (
    TASK_IN_PROGRESS,
    _append_log,
    _aware_utc,
    _increment_task,
    _lock_task,
    _require_state,
    _required_text,
)

UowFactory = Callable[[], UnitOfWork]

ISSUE_TYPES = {"blocker", "resource_request", "collaboration_support", "risk"}
ISSUE_SEVERITIES = {"low", "medium", "high", "critical"}
ISSUE_TRANSITIONS = {
    "processing": {"open"},
    "resolved": {"open", "processing"},
    "rejected": {"open", "processing"},
    "closed": {"resolved", "rejected"},
}


def issue_allowed_actions(issue: TaskIssue, actor_employee_no: str) -> list[str]:
    if actor_employee_no == issue.owner_employee_no:
        if issue.status == "open":
            return ["start_processing", "resolve", "reject"]
        if issue.status == "processing":
            return ["resolve", "reject"]
    if (
        actor_employee_no == issue.reported_by_employee_no
        and issue.status in {"resolved", "rejected"}
    ):
        return ["close"]
    return []


class TaskIssueService:
    """Create and transition task issues without mutating task or node status."""

    def __init__(self, uow_factory: UowFactory, clock: Clock = utc_now) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    def create(self, command: CreateTaskIssueCommand) -> TaskIssue:
        issue_type = _required_text(command.issue_type, "issue_type")
        severity = _required_text(command.severity, "severity")
        if issue_type not in ISSUE_TYPES:
            raise BusinessValidationError("issue_type is not supported")
        if severity not in ISSUE_SEVERITIES:
            raise BusinessValidationError("severity is not supported")
        title = _required_text(command.title, "title")
        description = _required_text(command.description, "description")
        if issue_type == "resource_request":
            _required_text(command.requested_resource or "", "requested_resource")
        now = _aware_utc(self._clock(), "clock")

        with self._uow_factory() as uow:
            task = _lock_task(uow, command.task_id, command.expected_task_version)
            _require_state(task, TASK_IN_PROGRESS)
            node = self._node(uow, task, command.node_id)
            self._require_reporter(uow, task, node, command.reported_by_employee_no)
            if uow.users.get_by_employee_no(command.owner_employee_no) is None:
                raise EntityNotFoundError("issue owner was not found")
            if command.source_progress_report_id is not None:
                source = uow.progress_reports.get_by_task_and_id(
                    task.task_id,
                    command.source_progress_report_id,
                )
                if source is None:
                    raise EntityNotFoundError("source progress report was not found")
                if source.node_id != command.node_id:
                    raise BusinessValidationError(
                        "source progress report must use the same node scope"
                    )

            _increment_task(task, now)
            issue = uow.task_issues.add(
                TaskIssue(
                    issue_id=command.issue_id,
                    task_id=task.task_id,
                    node_id=command.node_id,
                    source_progress_report_id=command.source_progress_report_id,
                    reported_by_employee_no=command.reported_by_employee_no,
                    issue_type=issue_type,
                    title=title,
                    description=description,
                    requested_resource=command.requested_resource,
                    severity=severity,
                    status="open",
                    owner_employee_no=command.owner_employee_no,
                    created_at=now,
                )
            )
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_IN_PROGRESS,
                action_type="task_issue_created",
                operator_employee_no=command.reported_by_employee_no,
                target_employee_no=command.owner_employee_no,
                operation_source=command.operation_source,
                now=now,
                business_ref_type="task_issue",
                business_ref_id=issue.issue_id,
            )
            uow.commit()
            return issue

    def transition(
        self,
        task_id: UUID,
        issue_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        target_status: str,
        reason: str | None = None,
    ) -> TaskIssue:
        if target_status not in ISSUE_TRANSITIONS:
            raise BusinessValidationError("unsupported task issue action")
        normalized_reason = None
        if target_status in {"resolved", "rejected", "closed"}:
            normalized_reason = _required_text(reason or "", "reason")
        now = _aware_utc(self._clock(), "clock")

        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_IN_PROGRESS)
            issue = uow.task_issues.get_by_task_and_id_for_update(task_id, issue_id)
            if issue is None:
                raise EntityNotFoundError("task issue was not found")
            if issue.status not in ISSUE_TRANSITIONS[target_status]:
                raise InvalidStateTransitionError(
                    f"task issue cannot transition from {issue.status} to {target_status}"
                )
            self._require_transition_actor(issue, actor_employee_no, target_status)

            if target_status == "processing":
                issue.processing_started_at = now
            elif target_status == "resolved":
                issue.resolved_at = now
                issue.resolved_by_employee_no = actor_employee_no
                issue.resolution_note = normalized_reason
            elif target_status == "rejected":
                issue.rejected_at = now
                issue.rejected_by_employee_no = actor_employee_no
                issue.resolution_note = normalized_reason
            else:
                issue.closed_at = now
                issue.closed_by_employee_no = actor_employee_no
            issue.status = target_status

            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_IN_PROGRESS,
                action_type=f"task_issue_{target_status}",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                reason=normalized_reason,
                now=now,
                business_ref_type="task_issue",
                business_ref_id=issue.issue_id,
            )
            uow.commit()
            return issue

    @staticmethod
    def _node(
        uow: UnitOfWork,
        task: Task,
        node_id: UUID | None,
    ) -> TaskNode | None:
        if node_id is None:
            return None
        node = uow.task_nodes.get_node(node_id)
        if node is None:
            raise EntityNotFoundError("task node was not found")
        if node.task_id != task.task_id:
            raise BusinessValidationError("task node does not belong to the task")
        return node

    @staticmethod
    def _require_reporter(
        uow: UnitOfWork,
        task: Task,
        node: TaskNode | None,
        employee_no: str,
    ) -> None:
        if employee_no in {task.creator_employee_no, task.main_assignee_employee_no}:
            return
        if node is not None and employee_no == node.owner_employee_no:
            return
        if node is not None and any(
            participant.employee_no == employee_no
            for participant in uow.task_nodes.list_participants(
                task.task_id,
                node.node_id,
            )
        ):
            return
        if node is None and any(
            participant.employee_no == employee_no
            for participant in uow.tasks.list_participants(task.task_id)
        ):
            return
        raise PermissionDeniedError("actor cannot report issues for this task scope")

    @staticmethod
    def _require_transition_actor(
        issue: TaskIssue,
        actor_employee_no: str,
        target_status: str,
    ) -> None:
        expected_actor = (
            issue.reported_by_employee_no
            if target_status == "closed"
            else issue.owner_employee_no
        )
        if actor_employee_no != expected_actor:
            role = "reporter" if target_status == "closed" else "owner"
            raise PermissionDeniedError(f"actor must be the task issue {role}")
