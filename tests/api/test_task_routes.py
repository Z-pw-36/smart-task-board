from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_task_node_workflow_service,
    get_task_query_service,
    get_task_workflow_service,
)
from app.main import app
from app.services.errors import PermissionDeniedError

NOW = datetime(2026, 8, 18, tzinfo=UTC)


def _task_result(task_id: UUID, status: str, version: int) -> SimpleNamespace:
    return SimpleNamespace(
        task_id=task_id,
        status=status,
        task_version=version,
        updated_at=NOW,
    )


def _node(task_id: UUID, node_id: UUID) -> dict[str, object]:
    return {
        "node_id": node_id,
        "task_id": task_id,
        "node_order": 1,
        "sort_weight": 0,
        "node_name": "Node",
        "action_detail": None,
        "tools_or_materials": None,
        "owner_employee_no": "E-ASSIGNEE",
        "planned_start_time": None,
        "planned_deadline": None,
        "estimated_hours": None,
        "actual_hours": None,
        "deliverable": None,
        "acceptance_criteria": None,
        "progress_percent": 0,
        "status": "pending",
        "completed_at": None,
    }


def _detail(task_id: UUID, node_id: UUID) -> dict[str, object]:
    return {
        "task_id": task_id,
        "task_no": None,
        "task_name": "Task",
        "task_description": None,
        "task_goal": None,
        "task_source": None,
        "creator_employee_no": "E-CREATOR",
        "main_assignee_employee_no": "E-ASSIGNEE",
        "report_to_employee_no": None,
        "report_to_level": None,
        "reviewer_employee_no": "E-REVIEWER",
        "department_id": None,
        "status": "draft",
        "start_time": None,
        "deadline": None,
        "estimated_hours": None,
        "actual_hours": None,
        "task_weight": None,
        "deliverable": None,
        "acceptance_criteria": None,
        "is_urgent": None,
        "report_cycle": None,
        "cancel_reason": None,
        "withdraw_reason": None,
        "close_reason": None,
        "merged_into_task_id": None,
        "task_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "confirmed_at": None,
        "sent_at": None,
        "accepted_at": None,
        "completed_at": None,
        "archived_at": None,
        "participants": [],
        "nodes": [_node(task_id, node_id)],
        "dependencies": [],
        "node_participants": [],
        "ai_extraction_records": [],
    }


@pytest.fixture
def route_context() -> Iterator[tuple[TestClient, MagicMock, MagicMock, MagicMock]]:
    task_id, node_id = uuid4(), uuid4()
    tasks = MagicMock()
    nodes = MagicMock()
    query = MagicMock()
    tasks.create_task_draft.return_value = _task_result(task_id, "draft", 1)
    query.get_task_detail.return_value = _detail(task_id, node_id)
    query.list_nodes.return_value = [_node(task_id, node_id)]
    query.get_node.return_value = _node(task_id, node_id)
    query.list_status_logs.return_value = {
        "items": [],
        "limit": 50,
        "offset": 0,
        "total": 0,
    }
    query.get_node_action_snapshot.return_value = {
        "task_id": task_id,
        "node_id": node_id,
        "task_status": "in_progress",
        "node_status": "in_progress",
        "progress_percent": 60,
        "task_version": 5,
    }
    app.dependency_overrides[get_task_workflow_service] = lambda: tasks
    app.dependency_overrides[get_task_node_workflow_service] = lambda: nodes
    app.dependency_overrides[get_task_query_service] = lambda: query
    try:
        with TestClient(app) as client:
            yield client, tasks, nodes, query
    finally:
        app.dependency_overrides.clear()


def test_create_route_builds_command_from_header(route_context) -> None:
    client, tasks, _, _ = route_context
    node_id = uuid4()
    response = client.post(
        "/api/v1/tasks",
        headers={"X-Employee-No": "  E-CREATOR  "},
        json={
            "task_name": "Task",
            "main_assignee_employee_no": "E-ASSIGNEE",
            "nodes": [{"node_id": str(node_id), "node_order": 1, "node_name": "Node"}],
        },
    )

    assert response.status_code == 201
    command = tasks.create_task_draft.call_args.args[0]
    assert command.creator_employee_no == "E-CREATOR"
    assert command.operation_source == "rest_api"
    assert command.nodes[0].node_id == node_id


@pytest.mark.parametrize(
    ("path", "method_name", "status_value", "version"),
    [
        ("submit-for-confirmation", "submit_for_confirmation", "pending_confirmation", 2),
        ("confirm-and-send", "confirm_and_send", "pending_acceptance", 3),
        ("confirm-self-assigned", "confirm_self_assigned", "in_progress", 3),
        ("accept", "accept_task", "in_progress", 4),
        ("resend", "resend_task", "pending_acceptance", 5),
        ("submit-completion", "submit_completion", "pending_review", 10),
        ("approve-completion", "approve_completion", "completed", 11),
    ],
)
def test_task_action_routes_forward_actor_version_and_fixed_source(
    route_context,
    path: str,
    method_name: str,
    status_value: str,
    version: int,
) -> None:
    client, tasks, _, _ = route_context
    task_id = uuid4()
    getattr(tasks, method_name).return_value = _task_result(task_id, status_value, version)

    response = client.post(
        f"/api/v1/tasks/{task_id}/actions/{path}",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"expected_task_version": version - 1},
    )

    assert response.status_code == 200
    getattr(tasks, method_name).assert_called_once_with(
        task_id,
        "E-ACTOR",
        version - 1,
        "rest_api",
    )
    assert response.json()["status"] == status_value


def test_return_route_forwards_trimmed_reason(route_context) -> None:
    client, tasks, _, _ = route_context
    task_id = uuid4()
    tasks.return_task.return_value = _task_result(task_id, "returned", 4)

    response = client.post(
        f"/api/v1/tasks/{task_id}/actions/return",
        headers={"X-Employee-No": "E-ASSIGNEE"},
        json={"expected_task_version": 3, "reason": "  revise  "},
    )

    assert response.status_code == 200
    tasks.return_task.assert_called_once_with(
        task_id,
        "E-ASSIGNEE",
        3,
        "rest_api",
        "revise",
    )


def test_node_routes_forward_identifiers_and_do_not_commit(route_context) -> None:
    client, _, nodes, query = route_context
    task_id, node_id = uuid4(), uuid4()
    query.get_node_action_snapshot.return_value.update(
        task_id=task_id,
        node_id=node_id,
    )
    headers = {"X-Employee-No": "E-OWNER"}

    start = client.post(
        f"/api/v1/tasks/{task_id}/nodes/{node_id}/actions/start",
        headers=headers,
        json={"expected_task_version": 4},
    )
    progress = client.patch(
        f"/api/v1/tasks/{task_id}/nodes/{node_id}/progress",
        headers=headers,
        json={
            "expected_task_version": 5,
            "progress_percent": 60,
            "actual_hours": "3.5",
        },
    )
    complete = client.post(
        f"/api/v1/tasks/{task_id}/nodes/{node_id}/actions/complete",
        headers=headers,
        json={"expected_task_version": 6},
    )

    assert [start.status_code, progress.status_code, complete.status_code] == [200, 200, 200]
    nodes.start_node.assert_called_once_with(task_id, node_id, "E-OWNER", 4, "rest_api")
    assert nodes.update_node_progress.call_args.args[:6] == (
        task_id,
        node_id,
        "E-OWNER",
        5,
        "rest_api",
        60,
    )
    nodes.complete_node.assert_called_once_with(task_id, node_id, "E-OWNER", 6, "rest_api")
    assert not hasattr(nodes, "commit") or not nodes.commit.called


def test_query_routes_forward_actor_and_pagination(route_context) -> None:
    client, _, _, query = route_context
    task_id, node_id = uuid4(), uuid4()
    headers = {"X-Employee-No": "E-READER"}

    detail = client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    listed = client.get(f"/api/v1/tasks/{task_id}/nodes", headers=headers)
    node = client.get(f"/api/v1/tasks/{task_id}/nodes/{node_id}", headers=headers)
    logs = client.get(
        f"/api/v1/tasks/{task_id}/status-logs?limit=10&offset=5",
        headers=headers,
    )

    assert [detail.status_code, listed.status_code, node.status_code, logs.status_code] == [
        200,
        200,
        200,
        200,
    ]
    query.get_task_detail.assert_called_once_with(task_id, "E-READER")
    query.list_nodes.assert_called_once_with(task_id, "E-READER")
    query.get_node.assert_called_once_with(task_id, node_id, "E-READER")
    query.list_status_logs.assert_called_once_with(
        task_id,
        "E-READER",
        limit=10,
        offset=5,
    )


@pytest.mark.parametrize("headers", [{}, {"X-Employee-No": "   "}])
def test_missing_or_blank_identity_is_401(route_context, headers: dict[str, str]) -> None:
    client, _, _, _ = route_context
    response = client.get(f"/api/v1/tasks/{uuid4()}", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_actor_cannot_be_supplied_in_json(route_context) -> None:
    client, tasks, _, _ = route_context
    response = client.post(
        "/api/v1/tasks",
        headers={"X-Employee-No": "E-CREATOR"},
        json={"task_name": "Task", "creator_employee_no": "E-OUTSIDER"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_validation_error"
    tasks.create_task_draft.assert_not_called()


def test_node_participant_header_does_not_bypass_service(route_context) -> None:
    client, _, nodes, _ = route_context
    task_id, node_id = uuid4(), uuid4()
    nodes.start_node.side_effect = PermissionDeniedError("actor cannot execute this task node")

    response = client.post(
        f"/api/v1/tasks/{task_id}/nodes/{node_id}/actions/start",
        headers={"X-Employee-No": "E-NODE-PARTICIPANT"},
        json={"expected_task_version": 4},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_openapi_and_swagger_expose_only_approved_contract(route_context) -> None:
    client, _, _, _ = route_context

    openapi_response = client.get("/openapi.json")
    docs_response = client.get("/docs")

    assert openapi_response.status_code == 200
    assert docs_response.status_code == 200
    specification = openapi_response.json()
    phase5_paths = {
        path: operations
        for path, operations in specification["paths"].items()
        if path.startswith("/api/v1")
    }
    assert len(phase5_paths) == 16
    for operations in phase5_paths.values():
        for operation in operations.values():
            header_names = {
                parameter["name"]
                for parameter in operation.get("parameters", [])
                if parameter["in"] == "header"
            }
            assert "X-Employee-No" in header_names
            assert "401" in operation["responses"]
            assert "422" in operation["responses"]

    serialized = openapi_response.text
    assert "pending_confirmation" in serialized
    assert "pending_acceptance" in serialized
    assert "ErrorResponse" in serialized
    assert "reject-completion" not in serialized
    assert "reopen-node" not in serialized
    assert "postgresql" not in serialized.lower()
    assert "password" not in serialized.lower()
