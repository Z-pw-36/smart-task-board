from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from app.models import Task, TaskIssue, TaskNode, User
from app.services import (
    BusinessValidationError,
    CreateTaskIssueCommand,
    InvalidStateTransitionError,
    PermissionDeniedError,
    TaskIssueService,
)

NOW = datetime(2026, 8, 19, 4, 0, tzinfo=UTC)


def _context(*, node: TaskNode | None = None):
    task = Task(
        task_id=uuid4(),
        task_name="Task",
        creator_employee_no="CREATOR",
        main_assignee_employee_no="ASSIGNEE",
        status="in_progress",
        task_version=7,
        created_at=NOW,
        updated_at=NOW,
    )
    if node is not None:
        node.task_id = task.task_id
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.__exit__.return_value = False
    uow.tasks.get_by_id_for_update.return_value = task
    uow.task_nodes.get_node.return_value = node
    uow.users.get_by_employee_no.return_value = User(
        employee_no="OWNER",
        name="Owner",
        role_type="employee",
        status="active",
    )
    uow.task_issues.add.side_effect = lambda value: value
    uow.task_status_logs.add.side_effect = lambda value: value
    service = TaskIssueService(Mock(return_value=uow), clock=lambda: NOW)
    return service, uow, task


def _command(task: Task, **overrides):
    values = {
        "task_id": task.task_id,
        "reported_by_employee_no": "ASSIGNEE",
        "expected_task_version": 7,
        "operation_source": "unit-test",
        "issue_type": "blocker",
        "title": "Blocked",
        "description": "Need access",
        "severity": "high",
        "owner_employee_no": "OWNER",
        **overrides,
    }
    return CreateTaskIssueCommand(**values)


def test_create_issue_is_open_versioned_and_does_not_change_task_status() -> None:
    service, uow, task = _context()

    issue = service.create(_command(task))

    assert issue.status == "open"
    assert task.status == "in_progress"
    assert task.task_version == 8
    log = uow.task_status_logs.add.call_args.args[0]
    assert (log.action_type, log.business_ref_type, log.business_ref_id) == (
        "task_issue_created",
        "task_issue",
        issue.issue_id,
    )


def test_resource_request_requires_requested_resource() -> None:
    service, _, task = _context()

    with pytest.raises(BusinessValidationError, match="requested_resource"):
        service.create(_command(task, issue_type="resource_request"))


def test_node_collaborator_may_create_issue() -> None:
    node = TaskNode(
        node_id=uuid4(),
        task_id=uuid4(),
        node_order=1,
        node_name="Node",
        owner_employee_no="OWNER",
    )
    service, uow, task = _context(node=node)
    uow.task_nodes.list_participants.return_value = [
        MagicMock(employee_no="COLLAB")
    ]

    issue = service.create(
        _command(
            task,
            node_id=node.node_id,
            reported_by_employee_no="COLLAB",
        )
    )

    assert issue.node_id == node.node_id


def test_issue_owner_and_reporter_complete_exact_lifecycle() -> None:
    service, uow, task = _context()
    issue = TaskIssue(
        issue_id=uuid4(),
        task_id=task.task_id,
        reported_by_employee_no="ASSIGNEE",
        issue_type="blocker",
        title="Blocked",
        description="Need access",
        severity="high",
        status="open",
        owner_employee_no="OWNER",
        created_at=NOW,
    )
    uow.task_issues.get_by_task_and_id_for_update.return_value = issue

    service.transition(
        task.task_id, issue.issue_id, "OWNER", 7, "unit-test", "processing"
    )
    assert (issue.status, issue.processing_started_at, task.task_version) == (
        "processing",
        NOW,
        8,
    )

    task.task_version = 8
    service.transition(
        task.task_id,
        issue.issue_id,
        "OWNER",
        8,
        "unit-test",
        "resolved",
        "Access granted",
    )
    assert (issue.status, issue.resolved_by_employee_no, issue.resolution_note) == (
        "resolved",
        "OWNER",
        "Access granted",
    )

    task.task_version = 9
    service.transition(
        task.task_id,
        issue.issue_id,
        "ASSIGNEE",
        9,
        "unit-test",
        "closed",
        "Verified",
    )
    assert (issue.status, issue.closed_by_employee_no, task.status) == (
        "closed",
        "ASSIGNEE",
        "in_progress",
    )


def test_illegal_transition_and_wrong_actor_do_not_commit() -> None:
    service, uow, task = _context()
    issue = TaskIssue(
        issue_id=uuid4(),
        task_id=task.task_id,
        reported_by_employee_no="ASSIGNEE",
        issue_type="risk",
        title="Risk",
        description="Risk",
        severity="low",
        status="open",
        owner_employee_no="OWNER",
    )
    uow.task_issues.get_by_task_and_id_for_update.return_value = issue

    with pytest.raises(InvalidStateTransitionError):
        service.transition(
            task.task_id,
            issue.issue_id,
            "ASSIGNEE",
            7,
            "unit-test",
            "closed",
            "No",
        )
    with pytest.raises(PermissionDeniedError):
        service.transition(
            task.task_id,
            issue.issue_id,
            "ASSIGNEE",
            7,
            "unit-test",
            "resolved",
            "No",
        )
    assert task.task_version == 7
    uow.commit.assert_not_called()


def test_closed_issue_is_terminal() -> None:
    service, uow, task = _context()
    issue = MagicMock(
        issue_id=uuid4(),
        task_id=task.task_id,
        status="closed",
        owner_employee_no="OWNER",
        reported_by_employee_no="ASSIGNEE",
    )
    uow.task_issues.get_by_task_and_id_for_update.return_value = issue

    with pytest.raises(InvalidStateTransitionError):
        service.transition(
            task.task_id,
            issue.issue_id,
            "OWNER",
            7,
            "unit-test",
            "processing",
        )
