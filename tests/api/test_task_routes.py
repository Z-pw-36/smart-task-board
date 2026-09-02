from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_intake_service,
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


def _review_result(
    task_id: UUID,
    *,
    review_status: str = "submitted",
    review_round: int = 1,
) -> SimpleNamespace:
    terminal = review_status != "submitted"
    return SimpleNamespace(
        completion_review_id=uuid4(),
        task_id=task_id,
        review_round=review_round,
        submitted_by_employee_no="E-ASSIGNEE",
        completion_note="Work completed",
        deliverable_summary="Release package",
        reviewer_employee_no="E-REVIEWER",
        review_status=review_status,
        review_result=review_status if terminal else None,
        reject_reason="Revise node" if review_status == "rejected" else None,
        rework_node_id=None,
        submitted_task_version=10,
        reviewed_task_version=11 if terminal else None,
        submitted_at=NOW,
        reviewed_at=NOW if terminal else None,
        is_legacy_import=False,
    )


def _change_request_result(
    task_id: UUID,
    *,
    request_id: UUID | None = None,
    request_status: str = "pending",
) -> SimpleNamespace:
    return SimpleNamespace(
        change_request_id=request_id or uuid4(),
        task_id=task_id,
        requester_employee_no="E-ASSIGNEE",
        patch_json={"task_name": "Updated task"},
        reason="Task facts changed",
        before_snapshot={"task_name": "Task"},
        after_snapshot={"task_name": "Updated task"},
        status=request_status,
        decision_by_employee_no="E-CREATOR" if request_status in {"approved", "rejected"} else None,
        decision_at=NOW if request_status in {"approved", "rejected"} else None,
        decision_comment="Looks right" if request_status == "approved" else None,
        cancelled_by_employee_no="E-ASSIGNEE" if request_status == "cancelled" else None,
        cancelled_at=NOW if request_status == "cancelled" else None,
        cancellation_reason="No longer needed" if request_status == "cancelled" else None,
        requester_task_version=4,
        base_task_version=4,
        created_at=NOW,
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
    intake = MagicMock()
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
    query.list_completion_reviews.return_value = {
        "items": [],
        "limit": 20,
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
    app.dependency_overrides[get_intake_service] = lambda: intake
    tasks._intake = intake
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


def test_completion_routes_forward_content_round_and_rework_scope(route_context) -> None:
    client, tasks, nodes, query = route_context
    task_id, node_id, review_id = uuid4(), uuid4(), uuid4()
    submitted = _review_result(task_id)
    submitted.completion_review_id = review_id
    rejected = _review_result(task_id, review_status="rejected")
    rejected.completion_review_id = review_id
    tasks.submit_completion.return_value = (
        _task_result(task_id, "pending_review", 10),
        submitted,
    )
    tasks.reject_completion.return_value = (
        _task_result(task_id, "in_progress", 11),
        rejected,
    )
    headers = {"X-Employee-No": "E-ACTOR"}

    submit = client.post(
        f"/api/v1/tasks/{task_id}/actions/submit-completion",
        headers=headers,
        json={
            "expected_task_version": 9,
            "completion_note": "  Work completed  ",
            "deliverable_summary": "  Release package  ",
        },
    )
    reject = client.post(
        f"/api/v1/tasks/{task_id}/actions/reject-completion",
        headers=headers,
        json={
            "expected_task_version": 10,
            "completion_review_id": str(review_id),
            "reject_reason": "  Revise node  ",
            "rework_node_id": str(node_id),
        },
    )
    reopened = client.post(
        f"/api/v1/tasks/{task_id}/nodes/{node_id}/actions/reopen",
        headers=headers,
        json={
            "expected_task_version": 11,
            "completion_review_id": str(review_id),
        },
    )

    assert [submit.status_code, reject.status_code, reopened.status_code] == [200, 200, 200]
    tasks.submit_completion.assert_called_once_with(
        task_id,
        "E-ACTOR",
        9,
        "rest_api",
        "Work completed",
        "Release package",
    )
    tasks.reject_completion.assert_called_once_with(
        task_id,
        "E-ACTOR",
        10,
        "rest_api",
        review_id,
        "Revise node",
        node_id,
    )
    nodes.reopen_node.assert_called_once_with(
        task_id,
        node_id,
        "E-ACTOR",
        11,
        "rest_api",
        review_id,
    )
    assert submit.json()["review"]["completion_review_id"] == str(review_id)
    assert reject.json()["review"]["review_status"] == "rejected"
    query.get_node_action_snapshot.assert_called_with(task_id, node_id, "E-ACTOR")


def test_approve_completion_requires_and_forwards_review_id(route_context) -> None:
    client, tasks, _, _ = route_context
    task_id, review_id = uuid4(), uuid4()
    approved = _review_result(task_id, review_status="approved")
    approved.completion_review_id = review_id
    tasks.approve_completion.return_value = (
        _task_result(task_id, "completed", 11),
        approved,
    )

    response = client.post(
        f"/api/v1/tasks/{task_id}/actions/approve-completion",
        headers={"X-Employee-No": "E-REVIEWER"},
        json={
            "expected_task_version": 10,
            "completion_review_id": str(review_id),
        },
    )

    assert response.status_code == 200
    tasks.approve_completion.assert_called_once_with(
        task_id,
        "E-REVIEWER",
        10,
        "rest_api",
        review_id,
    )
    assert response.json()["review"]["review_result"] == "approved"


def test_change_request_routes_forward_actor_version_and_required_reason(
    route_context,
) -> None:
    client, tasks, _, query = route_context
    task_id, request_id = uuid4(), uuid4()
    pending = _change_request_result(task_id, request_id=request_id)
    approved = _change_request_result(task_id, request_id=request_id, request_status="approved")
    rejected = _change_request_result(task_id, request_id=request_id, request_status="rejected")
    cancelled = _change_request_result(task_id, request_id=request_id, request_status="cancelled")
    tasks.submit_change_request.return_value = (_task_result(task_id, "in_progress", 4), pending)
    tasks.approve_change_request.return_value = (_task_result(task_id, "in_progress", 5), approved)
    tasks.reject_change_request.return_value = (_task_result(task_id, "in_progress", 4), rejected)
    tasks.cancel_change_request.return_value = (_task_result(task_id, "in_progress", 4), cancelled)
    query.list_change_requests.return_value = {
        "items": [vars(pending)],
        "limit": 20,
        "offset": 0,
        "total": 1,
    }
    query.get_change_request.return_value = vars(pending)

    headers = {"X-Employee-No": "E-ACTOR"}
    submit = client.post(
        f"/api/v1/tasks/{task_id}/change-requests",
        headers=headers,
        json={
            "expected_task_version": 4,
            "patch_json": {"task_name": "Updated task"},
            "reason": "  Task facts changed  ",
        },
    )
    listed = client.get(f"/api/v1/tasks/{task_id}/change-requests", headers=headers)
    detail = client.get(
        f"/api/v1/tasks/{task_id}/change-requests/{request_id}",
        headers=headers,
    )
    approve = client.post(
        f"/api/v1/tasks/{task_id}/change-requests/{request_id}/actions/approve",
        headers=headers,
        json={"expected_task_version": 4, "approval_comment": "  Looks right  "},
    )
    reject = client.post(
        f"/api/v1/tasks/{task_id}/change-requests/{request_id}/actions/reject",
        headers=headers,
        json={"expected_task_version": 4, "reason": "  Not aligned  "},
    )
    reject_without_reason = client.post(
        f"/api/v1/tasks/{task_id}/change-requests/{request_id}/actions/reject",
        headers=headers,
        json={"expected_task_version": 4, "approval_comment": "wrong field"},
    )
    cancel = client.post(
        f"/api/v1/tasks/{task_id}/change-requests/{request_id}/actions/cancel",
        headers=headers,
        json={"expected_task_version": 4, "reason": "  No longer needed  "},
    )

    assert [
        submit.status_code,
        listed.status_code,
        detail.status_code,
        approve.status_code,
        reject.status_code,
        reject_without_reason.status_code,
        cancel.status_code,
    ] == [201, 200, 200, 200, 200, 422, 200]
    tasks.submit_change_request.assert_called_once_with(
        task_id,
        "E-ACTOR",
        4,
        "rest_api",
        {"task_name": "Updated task"},
        "Task facts changed",
    )
    tasks.approve_change_request.assert_called_once_with(
        task_id,
        "E-ACTOR",
        4,
        "rest_api",
        request_id,
        "  Looks right  ",
    )
    tasks.reject_change_request.assert_called_once_with(
        task_id,
        "E-ACTOR",
        4,
        "rest_api",
        request_id,
        "Not aligned",
    )
    tasks.cancel_change_request.assert_called_once_with(
        task_id,
        "E-ACTOR",
        4,
        "rest_api",
        request_id,
        "No longer needed",
    )
    query.list_change_requests.assert_called_once_with(task_id, "E-ACTOR", limit=20, offset=0)
    query.get_change_request.assert_called_once_with(task_id, request_id, "E-ACTOR")


def test_extended_lifecycle_routes_forward_reasons_and_targets(route_context) -> None:
    client, tasks, _, _ = route_context
    task_id, target_task_id = uuid4(), uuid4()
    tasks.cancel_task.return_value = _task_result(task_id, "cancelled", 5)
    tasks.withdraw_task.return_value = _task_result(task_id, "withdrawn", 5)
    tasks.close_task.return_value = _task_result(task_id, "closed", 5)
    tasks.archive_task.return_value = _task_result(task_id, "archived", 5)
    tasks.restore_task.return_value = _task_result(task_id, "pending_confirmation", 6)
    tasks.merge_task.return_value = _task_result(task_id, "merged", 5)
    headers = {"X-Employee-No": "E-ACTOR"}

    cancel = client.post(
        f"/api/v1/tasks/{task_id}/actions/cancel",
        headers=headers,
        json={"expected_task_version": 4, "reason": "  Duplicate  "},
    )
    withdraw = client.post(
        f"/api/v1/tasks/{task_id}/actions/withdraw",
        headers=headers,
        json={"expected_task_version": 4, "reason": "  Cannot take it  "},
    )
    close = client.post(
        f"/api/v1/tasks/{task_id}/actions/close",
        headers=headers,
        json={"expected_task_version": 4, "reason": "  Obsolete  "},
    )
    archive = client.post(
        f"/api/v1/tasks/{task_id}/actions/archive",
        headers=headers,
        json={"expected_task_version": 4},
    )
    restore = client.post(
        f"/api/v1/tasks/{task_id}/actions/restore",
        headers=headers,
        json={"expected_task_version": 5, "reason": "  Resume  "},
    )
    merge = client.post(
        f"/api/v1/tasks/{task_id}/actions/merge",
        headers=headers,
        json={
            "expected_task_version": 4,
            "target_task_id": str(target_task_id),
            "reason": "  Consolidate  ",
        },
    )

    assert [
        cancel.status_code,
        withdraw.status_code,
        close.status_code,
        archive.status_code,
        restore.status_code,
        merge.status_code,
    ] == [200, 200, 200, 200, 200, 200]
    tasks.cancel_task.assert_called_once_with(task_id, "E-ACTOR", 4, "rest_api", "Duplicate")
    tasks.withdraw_task.assert_called_once_with(
        task_id,
        "E-ACTOR",
        4,
        "rest_api",
        "Cannot take it",
    )
    tasks.close_task.assert_called_once_with(task_id, "E-ACTOR", 4, "rest_api", "Obsolete")
    tasks.archive_task.assert_called_once_with(task_id, "E-ACTOR", 4, "rest_api")
    tasks.restore_task.assert_called_once_with(task_id, "E-ACTOR", 5, "rest_api", "Resume")
    tasks.merge_task.assert_called_once_with(
        task_id,
        "E-ACTOR",
        4,
        "rest_api",
        target_task_id,
        "Consolidate",
    )


def test_completion_requests_reject_blank_required_content(route_context) -> None:
    client, tasks, _, _ = route_context
    task_id = uuid4()

    response = client.post(
        f"/api/v1/tasks/{task_id}/actions/submit-completion",
        headers={"X-Employee-No": "E-ASSIGNEE"},
        json={
            "expected_task_version": 9,
            "completion_note": "   ",
            "deliverable_summary": "Release package",
        },
    )

    assert response.status_code == 422
    tasks.submit_completion.assert_not_called()


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


def test_task_planning_routes_are_main_assignee_service_contracts(route_context) -> None:
    client, tasks, _, _ = route_context
    intake = tasks._intake
    task_id = uuid4()
    first = uuid4()
    second = uuid4()
    disabled = uuid4()
    dependency_id = uuid4()
    ignored_dependency_id = uuid4()
    intake.suggest_task_plan.return_value = {
        "task_id": task_id,
        "suggested_nodes": [
            {
                "client_node_id": "draft-node-1",
                "node_order": 1,
                "node_name": "Prepare scope",
                "action_detail": "Confirm input scope.",
                "tools_or_materials": None,
                "suggested_owner_employee_no": "E-ASSIGNEE",
                "planned_start_time": None,
                "planned_deadline": "2026-08-25T08:00:00Z",
                "estimated_hours": None,
                "deliverable": "Scope note",
                "acceptance_criteria": "Scope is approved",
                "dependencies": [],
                "enabled": True,
            }
        ],
        "suggested_dependencies": [],
    }
    tasks.confirm_task_plan.return_value = _task_result(task_id, "in_progress", 5)

    suggested = client.post(
        f"/api/v1/tasks/{task_id}/planning/decompose",
        headers={"X-Employee-No": "E-ASSIGNEE"},
        json={"instructions": "make it execution ready"},
    )
    confirmed = client.post(
        f"/api/v1/tasks/{task_id}/planning/confirm",
        headers={"X-Employee-No": "E-ASSIGNEE"},
        json={
            "expected_task_version": 4,
            "nodes": [
                {
                    "node_id": str(first),
                    "node_order": 1,
                    "node_name": "Prepare scope",
                    "owner_employee_no": "E-ASSIGNEE",
                    "planned_deadline": "2026-08-25T08:00:00Z",
                    "deliverable": "Scope note",
                    "acceptance_criteria": "Scope is approved",
                    "enabled": True,
                },
                {
                    "node_id": str(second),
                    "node_order": 2,
                    "node_name": "Deliver result",
                    "owner_employee_no": "E-COLLAB",
                    "planned_deadline": "2026-08-26T08:00:00Z",
                    "enabled": True,
                },
                {
                    "node_id": str(disabled),
                    "node_order": 3,
                    "node_name": "Disabled suggestion",
                    "owner_employee_no": "E-ASSIGNEE",
                    "planned_deadline": "2026-08-27T08:00:00Z",
                    "enabled": False,
                },
            ],
            "dependencies": [
                {
                    "dependency_id": str(dependency_id),
                    "predecessor_node_id": str(first),
                    "successor_node_id": str(second),
                },
                {
                    "dependency_id": str(ignored_dependency_id),
                    "predecessor_node_id": str(second),
                    "successor_node_id": str(disabled),
                },
            ],
            "node_participants": [
                {
                    "node_id": str(second),
                    "employee_no": "E-COLLAB",
                    "participant_role": "collaborator",
                },
                {
                    "node_id": str(disabled),
                    "employee_no": "E-COLLAB",
                    "participant_role": "collaborator",
                },
            ],
        },
    )

    assert suggested.status_code == 200
    assert confirmed.status_code == 200
    intake.suggest_task_plan.assert_called_once_with(
        "E-ASSIGNEE",
        task_id,
        instructions="make it execution ready",
    )
    call = tasks.confirm_task_plan.call_args
    assert call.args[:4] == (task_id, "E-ASSIGNEE", 4, "rest_api")
    assert [node.node_id for node in call.args[4]] == [first, second]
    assert [dependency.dependency_id for dependency in call.args[5]] == [dependency_id]
    assert [participant.node_id for participant in call.args[6]] == [second]
    assert confirmed.json()["status"] == "in_progress"


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
    review_id = uuid4()
    query.get_completion_review.return_value = vars(_review_result(task_id))
    query.get_completion_review.return_value["completion_review_id"] = review_id
    reviews = client.get(
        f"/api/v1/tasks/{task_id}/completion-reviews?limit=10&offset=5",
        headers=headers,
    )
    review = client.get(
        f"/api/v1/tasks/{task_id}/completion-reviews/{review_id}",
        headers=headers,
    )

    assert [
        detail.status_code,
        listed.status_code,
        node.status_code,
        logs.status_code,
        reviews.status_code,
        review.status_code,
    ] == [
        200,
        200,
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
    query.list_completion_reviews.assert_called_once_with(
        task_id,
        "E-READER",
        limit=10,
        offset=5,
    )
    query.get_completion_review.assert_called_once_with(
        task_id,
        review_id,
        "E-READER",
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
    api_operations = {
        (method.upper(), path)
        for path, path_item in specification["paths"].items()
        if path.startswith("/api/v1")
        for method in path_item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    phase5_operations = {
        ("POST", "/api/v1/tasks"),
        ("GET", "/api/v1/tasks/{task_id}"),
        ("GET", "/api/v1/tasks/{task_id}/nodes"),
        ("GET", "/api/v1/tasks/{task_id}/nodes/{node_id}"),
        ("GET", "/api/v1/tasks/{task_id}/status-logs"),
        ("GET", "/api/v1/tasks/{task_id}/completion-reviews"),
        (
            "GET",
            "/api/v1/tasks/{task_id}/completion-reviews/{completion_review_id}",
        ),
        ("POST", "/api/v1/tasks/{task_id}/planning/decompose"),
        ("POST", "/api/v1/tasks/{task_id}/planning/confirm"),
        ("POST", "/api/v1/tasks/{task_id}/actions/submit-for-confirmation"),
        ("POST", "/api/v1/tasks/{task_id}/actions/confirm-and-send"),
        ("POST", "/api/v1/tasks/{task_id}/actions/confirm-self-assigned"),
        ("POST", "/api/v1/tasks/{task_id}/actions/accept"),
        ("POST", "/api/v1/tasks/{task_id}/actions/return"),
        ("POST", "/api/v1/tasks/{task_id}/actions/resend"),
        ("POST", "/api/v1/tasks/{task_id}/actions/submit-completion"),
        ("POST", "/api/v1/tasks/{task_id}/actions/approve-completion"),
        ("POST", "/api/v1/tasks/{task_id}/actions/reject-completion"),
        ("POST", "/api/v1/tasks/{task_id}/nodes/{node_id}/actions/start"),
        ("PATCH", "/api/v1/tasks/{task_id}/nodes/{node_id}/progress"),
        ("POST", "/api/v1/tasks/{task_id}/nodes/{node_id}/actions/complete"),
        ("POST", "/api/v1/tasks/{task_id}/nodes/{node_id}/actions/reopen"),
    }
    batch1_operations = {
        ("GET", "/api/v1/auth/prototype-users"),
        ("POST", "/api/v1/auth/prototype-login"),
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/token"),
        ("POST", "/api/v1/auth/refresh"),
        ("POST", "/api/v1/auth/revoke"),
        ("POST", "/api/v1/auth/logout"),
        ("GET", "/api/v1/me"),
        ("GET", "/api/v1/tasks"),
        ("GET", "/api/v1/tasks/inbox"),
        ("GET", "/api/v1/dashboard/summary"),
        ("GET", "/api/v1/tasks/{task_id}/available-actions"),
    }
    batch2_operations = {
        ("GET", "/api/v1/tasks/report-due"),
        ("POST", "/api/v1/tasks/{task_id}/progress-reports"),
        ("GET", "/api/v1/tasks/{task_id}/progress-reports"),
        (
            "GET",
            "/api/v1/tasks/{task_id}/progress-reports/{progress_report_id}",
        ),
        ("POST", "/api/v1/tasks/{task_id}/issues"),
        ("GET", "/api/v1/tasks/{task_id}/issues"),
        ("GET", "/api/v1/tasks/{task_id}/issues/{issue_id}"),
        (
            "POST",
            "/api/v1/tasks/{task_id}/issues/{issue_id}/actions/start-processing",
        ),
        ("POST", "/api/v1/tasks/{task_id}/issues/{issue_id}/actions/resolve"),
        ("POST", "/api/v1/tasks/{task_id}/issues/{issue_id}/actions/reject"),
        ("POST", "/api/v1/tasks/{task_id}/issues/{issue_id}/actions/close"),
    }
    wave2_operations = {
        ("POST", "/api/v1/tasks/{task_id}/change-requests"),
        ("GET", "/api/v1/tasks/{task_id}/change-requests"),
        (
            "GET",
            "/api/v1/tasks/{task_id}/change-requests/{change_request_id}",
        ),
        (
            "POST",
            "/api/v1/tasks/{task_id}/change-requests/{change_request_id}/actions/approve",
        ),
        (
            "POST",
            "/api/v1/tasks/{task_id}/change-requests/{change_request_id}/actions/reject",
        ),
        (
            "POST",
            "/api/v1/tasks/{task_id}/change-requests/{change_request_id}/actions/cancel",
        ),
        ("POST", "/api/v1/tasks/{task_id}/actions/cancel"),
        ("POST", "/api/v1/tasks/{task_id}/actions/withdraw"),
        ("POST", "/api/v1/tasks/{task_id}/actions/close"),
        ("POST", "/api/v1/tasks/{task_id}/actions/archive"),
        ("POST", "/api/v1/tasks/{task_id}/actions/restore"),
        ("POST", "/api/v1/tasks/{task_id}/actions/merge"),
    }
    business_operations = {
        ("GET", "/api/v1/system-parameters"),
        ("PUT", "/api/v1/system-parameters/{param_key}"),
        ("PUT", "/api/v1/organization/employee-profiles/{employee_no}"),
        ("POST", "/api/v1/organization/recommendations/assignees"),
        ("POST", "/api/v1/permissions/scopes"),
        ("GET", "/api/v1/permissions/scopes"),
        ("POST", "/api/v1/task-inputs"),
        ("POST", "/api/v1/task-inputs/{input_id}/extract"),
        ("GET", "/api/v1/task-inputs/{input_id}/extraction"),
        ("POST", "/api/v1/task-inputs/{input_id}/clarifications"),
        ("POST", "/api/v1/task-inputs/{input_id}/confirm-task"),
        ("POST", "/api/v1/performance-metrics"),
        ("GET", "/api/v1/performance-metrics"),
        ("POST", "/api/v1/tasks/{task_id}/performance-matches/suggest"),
        (
            "POST",
            "/api/v1/tasks/{task_id}/performance-matches/{performance_match_id}/confirm",
        ),
        ("POST", "/api/v1/analytics/workload/{employee_no}"),
        ("POST", "/api/v1/analytics/priorities"),
        ("POST", "/api/v1/analytics/conflicts/detect"),
        ("POST", "/api/v1/conflicts/{conflict_id}/actions/acknowledge"),
        ("POST", "/api/v1/conflicts/{conflict_id}/actions/resolve"),
        ("POST", "/api/v1/conflicts/{conflict_id}/actions/ignore"),
        ("POST", "/api/v1/reminders/scan"),
        ("POST", "/api/v1/notifications/send-pending"),
        ("GET", "/api/v1/notifications"),
        ("POST", "/api/v1/notifications/{notification_id}/read"),
        ("POST", "/api/v1/tasks/{task_id}/archive-snapshot"),
        ("GET", "/api/v1/archives/search"),
        ("GET", "/api/v1/tasks/{task_id}/similar-archives"),
        ("POST", "/api/v1/archives/{archive_id}/reuse"),
        ("GET", "/api/v1/operation-logs"),
    }
    assert len(phase5_operations) == 22
    assert phase5_operations <= api_operations
    assert batch1_operations <= api_operations
    assert batch2_operations <= api_operations
    assert wave2_operations <= api_operations
    assert business_operations <= api_operations
    assert len({path for path in specification["paths"] if path.startswith("/api/v1")}) == 81
    assert len(api_operations) == 87

    security_schemes = specification["components"]["securitySchemes"]
    bearer_schemes = {
        name
        for name, scheme in security_schemes.items()
        if scheme.get("type") == "http" and scheme.get("scheme") == "bearer"
    }
    assert len(bearer_schemes) == 1
    bearer_scheme = next(iter(bearer_schemes))
    public_operations = {
        ("GET", "/api/v1/auth/prototype-users"),
        ("POST", "/api/v1/auth/prototype-login"),
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/token"),
        ("POST", "/api/v1/auth/refresh"),
        ("POST", "/api/v1/auth/revoke"),
    }
    for method, path in api_operations:
        operation = specification["paths"][path][method.lower()]
        header_names = {
            parameter["name"]
            for parameter in operation.get("parameters", [])
            if parameter["in"] == "header"
        }
        assert "Authorization" not in header_names
        assert "X-Employee-No" not in header_names
        if (method, path) in public_operations:
            assert not operation.get("security")
        else:
            assert {bearer_scheme: []} in operation["security"]

    serialized = openapi_response.text
    assert "pending_confirmation" in serialized
    assert "pending_acceptance" in serialized
    assert "ErrorResponse" in serialized
    assert "reject-completion" in serialized
    assert "completion_review_id" in serialized
    assert "/actions/reopen" in serialized
    assert "reopen-node" not in serialized
    assert "retry-node" not in serialized
    assert "postgresql" not in serialized.lower()
    assert "password" not in serialized.lower()
