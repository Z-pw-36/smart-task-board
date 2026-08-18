from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.models import Task, TaskNode, TaskNodeDependency
from app.services.task_board_query import (
    TaskBoardQueryService,
    _node_actions,
    _task_actions,
)

NOW = datetime(2026, 8, 18, 8, 0, tzinfo=UTC)


def _task(status: str, **overrides: object) -> Task:
    values: dict[str, object] = {
        "task_id": uuid4(),
        "task_name": "Board task",
        "creator_employee_no": "E-CREATOR",
        "main_assignee_employee_no": "E-ASSIGNEE",
        "reviewer_employee_no": "E-REVIEWER",
        "status": status,
        "task_version": 3,
        "created_at": NOW - timedelta(days=1),
        "updated_at": NOW,
    }
    values.update(overrides)
    return Task(**values)


def _node(task: Task, status: str = "pending", **overrides: object) -> TaskNode:
    values: dict[str, object] = {
        "node_id": uuid4(),
        "task_id": task.task_id,
        "node_order": 1,
        "node_name": "Do work",
        "owner_employee_no": "E-OWNER",
        "status": status,
        "progress_percent": 0,
    }
    values.update(overrides)
    return TaskNode(**values)


def test_task_actions_match_phase4_state_and_actor_rules() -> None:
    node = _node(_task("draft"))
    draft = _task("draft")
    assert _task_actions(draft, "E-CREATOR", [node]) == ["submit_for_confirmation"]
    assert _task_actions(draft, "E-OUTSIDE", [node]) == []
    pending = _task("pending_confirmation")
    assert _task_actions(pending, "E-CREATOR", [node]) == ["confirm_and_send"]
    self_assigned = _task(
        "pending_confirmation", main_assignee_employee_no="E-CREATOR"
    )
    assert _task_actions(self_assigned, "E-CREATOR", [node]) == [
        "confirm_self_assigned"
    ]
    acceptance = _task("pending_acceptance")
    assert _task_actions(acceptance, "E-ASSIGNEE", [node]) == ["accept", "return"]
    assert _task_actions(_task("returned"), "E-CREATOR", [node]) == ["resend"]
    completed_node = _node(_task("in_progress"), status="completed")
    assert _task_actions(_task("in_progress"), "E-ASSIGNEE", [completed_node]) == [
        "submit_completion"
    ]
    assert _task_actions(_task("pending_review"), "E-REVIEWER", [node]) == [
        "approve_completion"
    ]


def test_node_actions_keep_owner_fallback_and_dependency_rules() -> None:
    task = _task("in_progress")
    predecessor = _node(task, status="pending", node_order=1)
    successor = _node(task, status="pending", node_order=2)
    dependency = TaskNodeDependency(
        dependency_id=uuid4(),
        task_id=task.task_id,
        predecessor_node_id=predecessor.node_id,
        successor_node_id=successor.node_id,
    )
    nodes = {predecessor.node_id: predecessor, successor.node_id: successor}
    assert _node_actions(task, successor, "E-OWNER", [dependency], nodes) == []
    predecessor.status = "completed"
    assert _node_actions(task, successor, "E-OWNER", [dependency], nodes) == [
        "start_node"
    ]
    successor.status = "in_progress"
    assert _node_actions(task, successor, "E-OWNER", [dependency], nodes) == [
        "update_node_progress",
        "complete_node",
    ]
    assert _node_actions(task, successor, "E-NODE-PARTICIPANT", [], nodes) == []
    successor.owner_employee_no = None
    assert _node_actions(task, successor, "E-ASSIGNEE", [], nodes) == [
        "update_node_progress",
        "complete_node",
    ]


def test_inbox_projects_task_and_node_actions_with_expected_version() -> None:
    service = TaskBoardQueryService(MagicMock(), clock=lambda: NOW)
    task = _task("in_progress", deadline=NOW - timedelta(hours=1))
    node = _node(task, status="in_progress")
    service._tasks = MagicMock()
    service._nodes = MagicMock()
    service._users = MagicMock()
    service._tasks.list_inbox_candidates.return_value = [task]
    service._tasks.list_participants.return_value = []
    service._nodes.list_nodes.return_value = [node]
    service._nodes.list_dependencies.return_value = []
    service._nodes.list_participants_by_task_id.return_value = [
        SimpleNamespace(employee_no="E-NODE-PARTICIPANT")
    ]
    service._users.list_by_employee_nos.return_value = [
        SimpleNamespace(employee_no="E-CREATOR", name="Creator"),
        SimpleNamespace(employee_no="E-ASSIGNEE", name="Assignee"),
    ]
    result = service.list_inbox(
        "E-OWNER", action_code=None, limit=20, offset=0
    )
    assert result["total"] == 2
    assert {item["action_code"] for item in result["items"]} == {
        "update_node",
        "complete_node",
    }
    assert all(item["expected_task_version"] == 3 for item in result["items"])
    assert all(item["is_overdue"] is True for item in result["items"])


def test_dashboard_uses_bounded_real_time_counts_and_seven_day_window() -> None:
    service = TaskBoardQueryService(MagicMock(), clock=lambda: NOW)
    service._tasks = MagicMock()
    service._nodes = MagicMock()
    service._users = MagicMock()
    service._tasks.list_recent_related.return_value = []
    service._tasks.list_inbox_candidates.return_value = []
    service._tasks.count_related.side_effect = [2, 3, 4, 5, 1]
    result = service.dashboard_summary("E-CREATOR")
    assert result == {
        "created_task_count": 2,
        "assigned_task_count": 3,
        "inbox_count": 0,
        "in_progress_count": 4,
        "due_within_7_days_count": 5,
        "overdue_count": 1,
        "due_window_days": 7,
        "recent_tasks": [],
    }
