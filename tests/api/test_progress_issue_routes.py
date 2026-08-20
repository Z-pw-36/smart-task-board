from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_progress_issue_query_service,
    get_progress_report_service,
    get_task_issue_service,
)
from app.main import app

NOW = datetime(2026, 8, 19, 2, 0, tzinfo=UTC)


def _report(task_id, report_id=None):
    return SimpleNamespace(
        progress_report_id=report_id or uuid4(),
        task_id=task_id,
        node_id=None,
        reporter_employee_no="ASSIGNEE",
        progress_percent=40,
        report_content="Progress",
        stage_result=None,
        difficulty=None,
        resource_request=None,
        actual_hours=None,
        corrects_report_id=None,
        report_period_start=NOW,
        report_period_end=NOW,
        task_version=6,
        operation_source="rest_api",
        created_at=NOW,
    )


def _issue(task_id, issue_id=None, status="open"):
    return SimpleNamespace(
        issue_id=issue_id or uuid4(),
        task_id=task_id,
        node_id=None,
        source_progress_report_id=None,
        reported_by_employee_no="ASSIGNEE",
        issue_type="blocker",
        title="Blocked",
        description="Need access",
        requested_resource=None,
        severity="high",
        status=status,
        owner_employee_no="OWNER",
        resolution_note=None,
        resolved_by_employee_no=None,
        rejected_by_employee_no=None,
        closed_by_employee_no=None,
        created_at=NOW,
        processing_started_at=None,
        resolved_at=None,
        rejected_at=None,
        closed_at=None,
    )


@pytest.fixture
def api_context() -> Iterator[tuple[TestClient, MagicMock, MagicMock, MagicMock]]:
    reports = MagicMock()
    issues = MagicMock()
    query = MagicMock()
    app.dependency_overrides[get_progress_report_service] = lambda: reports
    app.dependency_overrides[get_task_issue_service] = lambda: issues
    app.dependency_overrides[get_progress_issue_query_service] = lambda: query
    try:
        with TestClient(app) as client:
            yield client, reports, issues, query
    finally:
        app.dependency_overrides.clear()


def test_submit_progress_report_builds_versioned_actor_command(api_context) -> None:
    client, reports, _, _ = api_context
    task_id = uuid4()
    reports.submit.return_value = _report(task_id)

    response = client.post(
        f"/api/v1/tasks/{task_id}/progress-reports",
        headers={"X-Employee-No": "ASSIGNEE"},
        json={
            "expected_task_version": 5,
            "progress_percent": 40,
            "report_content": "Progress",
        },
    )

    assert response.status_code == 201
    command = reports.submit.call_args.args[0]
    assert (command.task_id, command.reporter_employee_no) == (task_id, "ASSIGNEE")
    assert command.expected_task_version == 5
    assert command.operation_source == "rest_api"


def test_progress_report_query_routes_forward_identity_and_pagination(api_context) -> None:
    client, _, _, query = api_context
    task_id, report_id = uuid4(), uuid4()
    payload = _report(task_id, report_id).__dict__
    query.list_reports.return_value = {
        "items": [payload],
        "limit": 10,
        "offset": 2,
        "total": 1,
    }
    query.get_report.return_value = payload

    listed = client.get(
        f"/api/v1/tasks/{task_id}/progress-reports?limit=10&offset=2",
        headers={"X-Employee-No": "VIEWER"},
    )
    fetched = client.get(
        f"/api/v1/tasks/{task_id}/progress-reports/{report_id}",
        headers={"X-Employee-No": "VIEWER"},
    )

    assert (listed.status_code, fetched.status_code) == (200, 200)
    query.list_reports.assert_called_once_with(
        task_id,
        "VIEWER",
        limit=10,
        offset=2,
    )
    query.get_report.assert_called_once_with(task_id, report_id, "VIEWER")


def test_create_issue_and_transition_routes_preserve_actor_and_version(api_context) -> None:
    client, _, issues, _ = api_context
    task_id, issue_id = uuid4(), uuid4()
    issue = _issue(task_id, issue_id)
    issues.create.return_value = issue
    issues.transition.return_value = issue

    created = client.post(
        f"/api/v1/tasks/{task_id}/issues",
        headers={"X-Employee-No": "ASSIGNEE"},
        json={
            "expected_task_version": 5,
            "issue_type": "blocker",
            "title": "Blocked",
            "description": "Need access",
            "severity": "high",
            "owner_employee_no": "OWNER",
        },
    )
    transitioned = client.post(
        f"/api/v1/tasks/{task_id}/issues/{issue_id}/actions/start-processing",
        headers={"X-Employee-No": "OWNER"},
        json={"expected_task_version": 6},
    )

    assert (created.status_code, transitioned.status_code) == (201, 200)
    create_command = issues.create.call_args.args[0]
    assert create_command.reported_by_employee_no == "ASSIGNEE"
    assert issues.transition.call_args.args[:7] == (
        task_id,
        issue_id,
        "OWNER",
        6,
        "rest_api",
        "processing",
        None,
    )


def test_issue_list_detail_and_report_due_are_read_only(api_context) -> None:
    client, _, _, query = api_context
    task_id, issue_id = uuid4(), uuid4()
    issue_payload = {
        **_issue(task_id, issue_id).__dict__,
        "allowed_actions": ["start_processing", "resolve", "reject"],
    }
    query.list_issues.return_value = {
        "items": [issue_payload],
        "limit": 50,
        "offset": 0,
        "total": 1,
    }
    query.get_issue.return_value = issue_payload
    query.list_report_due.return_value = {
        "items": [],
        "total": 0,
        "calculated_at": NOW,
    }

    listed = client.get(
        f"/api/v1/tasks/{task_id}/issues?status=open",
        headers={"X-Employee-No": "ASSIGNEE"},
    )
    fetched = client.get(
        f"/api/v1/tasks/{task_id}/issues/{issue_id}",
        headers={"X-Employee-No": "ASSIGNEE"},
    )
    due = client.get(
        "/api/v1/tasks/report-due",
        headers={"X-Employee-No": "ASSIGNEE"},
    )

    assert (listed.status_code, fetched.status_code, due.status_code) == (200, 200, 200)
    query.list_issues.assert_called_once_with(
        task_id,
        "ASSIGNEE",
        status="open",
        limit=50,
        offset=0,
    )
    query.list_report_due.assert_called_once_with("ASSIGNEE")
