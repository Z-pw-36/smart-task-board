from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_task_board_query_service
from app.main import app

NOW = datetime(2026, 8, 18, 8, 0, tzinfo=UTC)


def _summary(task_id=None) -> dict[str, object]:
    return {
        "task_id": task_id or uuid4(),
        "task_no": None,
        "task_name": "Task",
        "status": "in_progress",
        "deadline": NOW,
        "is_urgent": True,
        "task_weight": 3,
        "task_version": 4,
        "creator": {"employee_no": "E-CREATOR", "name": "Creator"},
        "main_assignee": {"employee_no": "E-ACTOR", "name": "Actor"},
        "current_user_relations": ["assigned"],
        "allowed_actions": [],
        "is_overdue": False,
        "days_until_deadline": 0,
        "created_at": NOW,
        "updated_at": NOW,
    }


@pytest.fixture
def board_context():
    service = MagicMock()
    app.dependency_overrides[get_task_board_query_service] = lambda: service
    try:
        yield TestClient(app), service
    finally:
        app.dependency_overrides.clear()


def test_task_list_forwards_bounded_filters_and_actor(board_context) -> None:
    client, service = board_context
    service.list_tasks.return_value = {
        "items": [_summary()],
        "limit": 10,
        "offset": 5,
        "total": 1,
    }
    response = client.get(
        "/api/v1/tasks",
        headers={"X-Employee-No": "E-ACTOR"},
        params={
            "relation": "assigned",
            "status": "in_progress",
            "search": "Task",
            "deadline_from": "2026-08-01",
            "deadline_to": "2026-08-31",
            "limit": 10,
            "offset": 5,
        },
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["current_user_relations"] == ["assigned"]
    service.list_tasks.assert_called_once()
    args, kwargs = service.list_tasks.call_args
    assert args == ("E-ACTOR",)
    assert kwargs["relation"] == "assigned"
    assert kwargs["task_status"] == "in_progress"
    assert kwargs["limit"] == 10


def test_task_list_rejects_unbounded_limit_before_service(board_context) -> None:
    client, service = board_context
    response = client.get(
        "/api/v1/tasks?limit=101", headers={"X-Employee-No": "E-ACTOR"}
    )
    assert response.status_code == 422
    service.list_tasks.assert_not_called()


def test_inbox_returns_server_endpoint_version_and_allowed_actions(board_context) -> None:
    client, service = board_context
    task = _summary()
    service.list_inbox.return_value = {
        "items": [
            {
                "inbox_item_type": "accept_task",
                "action_code": "accept_task",
                "task": task,
                "node": None,
                "reason": "Task is waiting for the main assignee.",
                "expected_task_version": 4,
                "endpoint": f"/api/v1/tasks/{task['task_id']}/actions/accept",
                "allowed_actions": ["accept", "return"],
                "is_overdue": False,
                "relevant_at": NOW,
            }
        ],
        "limit": 20,
        "offset": 0,
        "total": 1,
    }
    response = client.get(
        "/api/v1/tasks/inbox?action_code=accept_task",
        headers={"X-Employee-No": "E-ACTOR"},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["allowed_actions"] == ["accept", "return"]
    service.list_inbox.assert_called_once_with(
        "E-ACTOR", action_code="accept_task", limit=20, offset=0
    )


def test_available_actions_are_always_projected_by_backend(board_context) -> None:
    client, service = board_context
    task_id, node_id = uuid4(), uuid4()
    service.available_actions.return_value = {
        "task_id": task_id,
        "task_version": 8,
        "allowed_actions": ["submit_completion"],
        "nodes": [{"node_id": node_id, "allowed_actions": []}],
    }
    response = client.get(
        f"/api/v1/tasks/{task_id}/available-actions",
        headers={"X-Employee-No": "E-ACTOR"},
    )
    assert response.status_code == 200
    assert response.json()["allowed_actions"] == ["submit_completion"]


def test_dashboard_summary_is_current_user_only_and_has_fixed_window(board_context) -> None:
    client, service = board_context
    service.dashboard_summary.return_value = {
        "created_task_count": 1,
        "assigned_task_count": 2,
        "inbox_count": 3,
        "in_progress_count": 4,
        "due_within_7_days_count": 5,
        "overdue_count": 6,
        "report_due_count": 7,
        "open_issue_count": 8,
        "due_window_days": 7,
        "recent_tasks": [],
    }
    response = client.get(
        "/api/v1/dashboard/summary", headers={"X-Employee-No": "E-ACTOR"}
    )
    assert response.status_code == 200
    assert response.json()["due_window_days"] == 7
    service.dashboard_summary.assert_called_once_with("E-ACTOR")
