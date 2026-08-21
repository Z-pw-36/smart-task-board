from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from app.models import Task, TaskNode, TaskNodeDependency, TaskParticipant, User
from app.services import (
    DependencyCycleError,
    PermissionDeniedError,
    TaskVersionConflictError,
    TaskWorkflowService,
)

NOW = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)


def _task(*, status: str = "in_progress", version: int = 3) -> Task:
    return Task(
        task_id=uuid4(),
        task_name="Original task",
        task_description="Description",
        creator_employee_no="CREATOR",
        main_assignee_employee_no="ASSIGNEE",
        reviewer_employee_no="REVIEWER",
        status=status,
        task_version=version,
        created_at=NOW,
        updated_at=NOW,
    )


def _node(task_id, *, node_id=None, order=1, status="pending", progress=0) -> TaskNode:
    return TaskNode(
        task_id=task_id,
        node_id=node_id or uuid4(),
        node_order=order,
        node_name=f"Node {order}",
        status=status,
        progress_percent=progress,
    )


def _context(
    task: Task,
    *,
    nodes: list[TaskNode] | None = None,
    dependencies: list[TaskNodeDependency] | None = None,
) -> tuple[TaskWorkflowService, MagicMock]:
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.__exit__.return_value = False
    uow.tasks.get_by_id_for_update.return_value = task
    uow.tasks.list_participants.return_value = [
        TaskParticipant(
            task_id=task.task_id,
            employee_no="ASSIGNEE",
            participant_role="assignee",
            is_primary=True,
        )
    ]
    uow.tasks.find_participant.return_value = uow.tasks.list_participants.return_value[0]
    uow.task_nodes.list_nodes.return_value = nodes or []
    uow.task_nodes.list_dependencies.return_value = dependencies or []
    uow.task_nodes.list_participants_by_task_id.return_value = []
    uow.task_issues.has_non_closed.return_value = False
    uow.task_status_logs.add.side_effect = lambda value: value
    uow.task_change_requests.add.side_effect = lambda value: value
    uow.task_change_requests.get_pending_for_update.return_value = None
    uow.task_change_requests.get_pending.return_value = None
    uow.task_change_requests.get_by_task_and_id_for_update.return_value = None
    uow.users.get_by_employee_no.return_value = User(
        employee_no="known",
        name="Known",
        role_type="employee",
        status="active",
    )
    return TaskWorkflowService(Mock(return_value=uow), clock=lambda: NOW), uow


def test_submit_change_request_captures_before_after_without_changing_task() -> None:
    task = _task()
    service, uow = _context(task)

    result = service.submit_change_request(
        task.task_id,
        "ASSIGNEE",
        task.task_version,
        "unit-test",
        {"task_name": "Updated task"},
        "Deadline and title clarified",
    )

    saved_task, request = result
    assert saved_task is task
    assert request.status == "pending"
    assert request.base_task_version == 3
    assert request.before_snapshot["task_name"] == "Original task"
    assert request.after_snapshot["task_name"] == "Updated task"
    assert task.task_name == "Original task"
    uow.commit.assert_called_once_with()
    assert uow.task_status_logs.add.call_args.args[0].action_type == "change_requested"


def test_change_request_approval_applies_atomically_and_increments_version() -> None:
    task = _task()
    service, uow = _context(task)
    _, request = service.submit_change_request(
        task.task_id,
        "ASSIGNEE",
        task.task_version,
        "unit-test",
        {"task_name": "Updated task"},
        "Clarify title",
    )
    uow.commit.reset_mock()
    uow.tasks.get_by_id_for_update.return_value = task
    uow.task_change_requests.get_by_task_and_id_for_update.return_value = request

    saved_task, saved_request = service.approve_change_request(
        task.task_id,
        "CREATOR",
        task.task_version,
        "unit-test",
        request.change_request_id,
        "Approved after review",
    )

    assert saved_task is task
    assert saved_request is request
    assert task.task_name == "Updated task"
    assert task.task_version == 4
    assert request.status == "approved"
    assert request.decision_by_employee_no == "CREATOR"
    assert uow.commit.call_count == 1
    assert uow.task_status_logs.add.call_args.args[0].action_type == "change_approved"


def test_reject_and_cancel_require_reason_and_only_pending_request() -> None:
    task = _task()
    service, uow = _context(task)
    _, request = service.submit_change_request(
        task.task_id,
        "ASSIGNEE",
        task.task_version,
        "unit-test",
        {"deadline": "2026-08-30T09:00:00+00:00"},
        "Need more time",
    )
    uow.commit.reset_mock()
    uow.task_change_requests.get_by_task_and_id_for_update.return_value = request

    with pytest.raises(PermissionDeniedError):
        service.reject_change_request(
            task.task_id,
            "ASSIGNEE",
            task.task_version,
            "unit-test",
            request.change_request_id,
            "No",
        )
    with pytest.raises(PermissionDeniedError):
        service.cancel_change_request(
            task.task_id,
            "CREATOR",
            task.task_version,
            "unit-test",
            request.change_request_id,
            "No",
        )
    assert request.status == "pending"
    assert uow.commit.call_count == 0

    _, cancelled = service.cancel_change_request(
        task.task_id,
        "ASSIGNEE",
        task.task_version,
        "unit-test",
        request.change_request_id,
        "No longer needed",
    )
    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_by_employee_no == "ASSIGNEE"


def test_approval_rejects_dependency_cycle_before_any_mutation() -> None:
    task = _task()
    first = _node(task.task_id, order=1)
    second = _node(task.task_id, order=2)
    existing = TaskNodeDependency(
        task_id=task.task_id,
        dependency_id=uuid4(),
        predecessor_node_id=first.node_id,
        successor_node_id=second.node_id,
        dependency_type="finish_to_start",
    )
    service, uow = _context(task, nodes=[first, second], dependencies=[existing])
    _, request = service.submit_change_request(
        task.task_id,
        "ASSIGNEE",
        task.task_version,
        "unit-test",
        {"task_name": "Cycle candidate"},
        "Add a dependency",
    )
    request.patch_json = {
        "dependencies": [
            {
                "dependency_id": str(existing.dependency_id),
                "predecessor_node_id": str(first.node_id),
                "successor_node_id": str(second.node_id),
                "dependency_type": "finish_to_start",
            },
            {
                "dependency_id": str(uuid4()),
                "predecessor_node_id": str(second.node_id),
                "successor_node_id": str(first.node_id),
                "dependency_type": "finish_to_start",
            },
        ]
    }
    uow.commit.reset_mock()
    uow.task_change_requests.get_by_task_and_id_for_update.return_value = request

    with pytest.raises(DependencyCycleError):
        service.approve_change_request(
            task.task_id,
            "CREATOR",
            task.task_version,
            "unit-test",
            request.change_request_id,
        )

    assert request.status == "pending"
    assert task.task_version == 3
    assert uow.commit.call_count == 0


def test_change_request_adds_node_with_server_generated_explicit_id() -> None:
    task = _task()
    existing_node = _node(task.task_id, order=1)
    service, uow = _context(task, nodes=[existing_node])

    _, request = service.submit_change_request(
        task.task_id,
        "ASSIGNEE",
        task.task_version,
        "unit-test",
        {
            "nodes": {
                "add": [
                    {
                        "node_order": 2,
                        "node_name": "New node",
                        "owner_employee_no": "ASSIGNEE",
                    }
                ]
            }
        },
        "Add missing execution step",
    )

    added_node_id = request.patch_json["nodes"]["add"][0]["node_id"]
    assert added_node_id == request.after_snapshot["nodes"][1]["node_id"]

    uow.commit.reset_mock()
    uow.task_change_requests.get_by_task_and_id_for_update.return_value = request

    service.approve_change_request(
        task.task_id,
        "CREATOR",
        task.task_version,
        "unit-test",
        request.change_request_id,
    )

    created_node = uow.task_nodes.add_node.call_args.args[0]
    assert str(created_node.node_id) == added_node_id
    assert created_node.node_name == "New node"


def test_lifecycle_guards_version_role_and_restore_status() -> None:
    task = _task(status="in_progress", version=2)
    service, uow = _context(task)

    with pytest.raises(PermissionDeniedError):
        service.withdraw_task(task.task_id, "OUTSIDER", 2, "unit-test", "No longer assigned")
    with pytest.raises(TaskVersionConflictError):
        service.cancel_task(task.task_id, "CREATOR", 1, "unit-test", "Duplicate")

    cancelled = service.cancel_task(task.task_id, "CREATOR", 2, "unit-test", "Stopped")
    assert cancelled.status == "cancelled"
    assert cancelled.cancel_reason == "Stopped"
    restored = service.restore_task(task.task_id, "CREATOR", 3, "unit-test", "Resume work")
    assert restored.status == "pending_confirmation"
    assert restored.task_version == 4
