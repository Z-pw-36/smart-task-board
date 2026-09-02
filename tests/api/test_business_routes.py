from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_archive_reuse_service,
    get_audit_query_service,
    get_intake_service,
    get_notification_service,
    get_performance_metric_service,
    get_permission_scope_service,
    get_planning_analytics_service,
    get_system_parameter_service,
)
from app.main import app

NOW = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)


def _task_result(task_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        task_id=task_id or uuid4(),
        status="draft",
        task_version=1,
        updated_at=NOW,
    )


def _metric(metric_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        metric_id=metric_id or uuid4(),
        metric_type="quality",
        period=None,
        business_unit=None,
        sequence_no=None,
        dimension=None,
        metric_name="Release quality",
        definition_formula=None,
        weight=Decimal("1"),
        target_value=None,
        deliverable=None,
        data_source=None,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _intake_result(input_id: UUID | None = None, extraction_id: UUID | None = None):
    return SimpleNamespace(
        task_input=SimpleNamespace(
            input_id=input_id or uuid4(),
            input_type="text",
            raw_text="Task title",
            asr_text=None,
            source_channel="api",
            submitted_by_employee_no="E-ACTOR",
            submitted_at=NOW,
        ),
        extraction=SimpleNamespace(
            extraction_id=extraction_id or uuid4(),
            extracted_json={"task_name": "Task title"},
            missing_fields=[],
            low_confidence_fields=[],
            confirm_questions=[],
            confidence_score=Decimal("0.95"),
        ),
    )


@pytest.fixture
def business_context() -> Iterator[tuple[TestClient, dict[str, MagicMock]]]:
    services = {
        "parameters": MagicMock(),
        "permissions": MagicMock(),
        "intake": MagicMock(),
        "metrics": MagicMock(),
        "planning": MagicMock(),
        "notifications": MagicMock(),
        "archive": MagicMock(),
        "audit": MagicMock(),
    }
    app.dependency_overrides[get_system_parameter_service] = lambda: services["parameters"]
    app.dependency_overrides[get_permission_scope_service] = lambda: services["permissions"]
    app.dependency_overrides[get_intake_service] = lambda: services["intake"]
    app.dependency_overrides[get_performance_metric_service] = lambda: services["metrics"]
    app.dependency_overrides[get_planning_analytics_service] = lambda: services["planning"]
    app.dependency_overrides[get_notification_service] = lambda: services["notifications"]
    app.dependency_overrides[get_archive_reuse_service] = lambda: services["archive"]
    app.dependency_overrides[get_audit_query_service] = lambda: services["audit"]
    try:
        with TestClient(app) as client:
            yield client, services
    finally:
        app.dependency_overrides.clear()


def test_parameter_permission_and_intake_routes_forward_actor(
    business_context,
) -> None:
    client, services = business_context
    parameter_id = uuid4()
    scope_id = uuid4()
    intake_id = uuid4()
    extraction_id = uuid4()
    services["parameters"].upsert_parameter.return_value = SimpleNamespace(
        parameter_id=parameter_id,
        param_key="daily_capacity_hours",
        param_name="Daily capacity hours",
        param_value="6",
        param_type="number",
        module="workload",
        description=None,
        is_active=True,
        updated_by_employee_no="E-ACTOR",
        updated_at=NOW,
    )
    services["permissions"].grant_scope.return_value = SimpleNamespace(
        authorized_scope_id=uuid4(),
        employee_no="E-TARGET",
        scope_type="department",
        scope_id=str(scope_id),
        permission_type="view",
        valid_from=NOW,
        valid_to=None,
        status="active",
        created_by_employee_no="E-ACTOR",
        created_at=NOW,
    )
    services["intake"].submit_input.return_value = _intake_result(intake_id, extraction_id)

    parameter = client.put(
        "/api/v1/system-parameters/daily_capacity_hours",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"param_value": "6", "param_type": "number", "module": "workload"},
    )
    scope = client.post(
        "/api/v1/permissions/scopes",
        headers={"X-Employee-No": "E-ACTOR"},
        json={
            "employee_no": "E-TARGET",
            "scope_type": "department",
            "scope_id": str(scope_id),
            "permission_type": "view",
            "valid_from": NOW.isoformat(),
        },
    )
    intake = client.post(
        "/api/v1/task-inputs",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"input_id": str(intake_id), "raw_text": "Task title"},
    )

    assert [parameter.status_code, scope.status_code, intake.status_code] == [200, 201, 201]
    services["parameters"].upsert_parameter.assert_called_once_with(
        "E-ACTOR",
        "daily_capacity_hours",
        value="6",
        param_type="number",
        module="workload",
        name=None,
        description=None,
        is_active=True,
    )
    services["permissions"].grant_scope.assert_called_once()
    assert services["permissions"].grant_scope.call_args.kwargs["employee_no"] == "E-TARGET"
    services["intake"].submit_input.assert_called_once_with(
        "E-ACTOR",
        input_id=intake_id,
        input_type="text",
        raw_text="Task title",
        voice_file_url=None,
        source_channel="api",
    )
    assert intake.json()["extraction_id"] == str(extraction_id)


def test_dev07_task_input_voice_retry_and_latest_extraction_routes(
    business_context,
) -> None:
    client, services = business_context
    intake_id = uuid4()
    first_extraction_id = uuid4()
    latest_extraction_id = uuid4()
    services["intake"].submit_input.return_value = _intake_result(intake_id, first_extraction_id)
    services["intake"].retry_extraction.return_value = _intake_result(
        intake_id,
        latest_extraction_id,
    )
    services["intake"].get_latest_extraction.return_value = _intake_result(
        intake_id,
        latest_extraction_id,
    )

    voice = client.post(
        "/api/v1/task-inputs",
        headers={"X-Employee-No": "E-ACTOR"},
        json={
            "input_id": str(intake_id),
            "input_type": "voice",
            "raw_text": "浏览器语音转写文本",
            "source_channel": "web",
        },
    )
    retried = client.post(
        f"/api/v1/task-inputs/{intake_id}/extract",
        headers={"X-Employee-No": "E-ACTOR"},
    )
    latest = client.get(
        f"/api/v1/task-inputs/{intake_id}/extraction",
        headers={"X-Employee-No": "E-ACTOR"},
    )

    assert [voice.status_code, retried.status_code, latest.status_code] == [201, 200, 200]
    services["intake"].submit_input.assert_called_once_with(
        "E-ACTOR",
        input_id=intake_id,
        input_type="voice",
        raw_text="浏览器语音转写文本",
        voice_file_url=None,
        source_channel="web",
    )
    services["intake"].retry_extraction.assert_called_once_with("E-ACTOR", intake_id)
    services["intake"].get_latest_extraction.assert_called_once_with("E-ACTOR", intake_id)
    assert latest.json()["job_status"] == "succeeded"
    assert latest.json()["extraction_id"] == str(latest_extraction_id)


def test_dev07_task_input_rejects_empty_and_overlong_payloads(
    business_context,
) -> None:
    client, services = business_context

    empty = client.post(
        "/api/v1/task-inputs",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"raw_text": "   ", "source_channel": "web"},
    )
    overlong = client.post(
        "/api/v1/task-inputs",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"raw_text": "字" * 4001, "source_channel": "web"},
    )

    assert [empty.status_code, overlong.status_code] == [422, 422]
    services["intake"].submit_input.assert_not_called()


def test_ai_confirmation_metric_and_planning_routes_forward_identifiers(
    business_context,
) -> None:
    client, services = business_context
    task_id = uuid4()
    extraction_id = uuid4()
    metric_id = uuid4()
    match_id = uuid4()
    services["intake"].create_draft_from_extraction.return_value = _task_result(task_id)
    services["metrics"].create_metric.return_value = _metric(metric_id)
    services["metrics"].suggest_matches.return_value = [
        SimpleNamespace(
            performance_match_id=match_id,
            task_id=task_id,
            metric_id=metric_id,
            type_score=Decimal("80"),
            business_unit_score=Decimal("60"),
            metric_name_score=Decimal("80"),
            definition_formula_score=Decimal("50"),
            deliverable_score=Decimal("90"),
            total_score=Decimal("72"),
            match_level="weak",
            match_reason="deterministic token overlap",
            is_confirmed=False,
            confirmed_by_employee_no=None,
            confirmed_at=None,
            algorithm_version="deterministic-token-overlap-v1",
            created_at=NOW,
            updated_at=NOW,
        )
    ]
    services["planning"].calculate_workload.return_value = SimpleNamespace(
        workload_snapshot_id=uuid4(),
        employee_no="E-ASSIGNEE",
        period_start=NOW,
        period_end=NOW,
        remaining_hours_sum=Decimal("4"),
        available_hours=Decimal("8"),
        active_task_count=1,
        active_task_weight_sum=Decimal("3"),
        urgent_task_count=0,
        blocked_task_count=0,
        overdue_task_count=0,
        hours_pressure=Decimal("50"),
        weight_pressure=Decimal("100"),
        count_pressure=Decimal("20"),
        urgent_pressure=Decimal("0"),
        blocked_overdue_pressure=Decimal("0"),
        workload_score=Decimal("48"),
        workload_level="normal",
        parameter_snapshot={},
        calculated_at=NOW,
    )

    confirmed = client.post(
        f"/api/v1/task-inputs/{uuid4()}/confirm-task",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"extraction_id": str(extraction_id), "task_id": str(task_id)},
    )
    metric = client.post(
        "/api/v1/performance-metrics",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"metric_type": "quality", "metric_name": "Release quality", "weight": "1"},
    )
    matches = client.post(
        f"/api/v1/tasks/{task_id}/performance-matches/suggest?limit=1",
        headers={"X-Employee-No": "E-ACTOR"},
    )
    workload = client.post(
        "/api/v1/analytics/workload/E-ASSIGNEE",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"period_start": NOW.isoformat(), "period_end": NOW.isoformat()},
    )

    status_codes = [
        confirmed.status_code,
        metric.status_code,
        matches.status_code,
        workload.status_code,
    ]
    assert status_codes == [
        201,
        201,
        200,
        200,
    ]
    services["intake"].create_draft_from_extraction.assert_called_once()
    assert services["intake"].create_draft_from_extraction.call_args.kwargs["task_id"] == task_id
    services["metrics"].create_metric.assert_called_once()
    services["metrics"].suggest_matches.assert_called_once_with("E-ACTOR", task_id, 1)
    services["planning"].calculate_workload.assert_called_once_with(
        "E-ACTOR", "E-ASSIGNEE", NOW, NOW
    )
    assert matches.json()[0]["performance_match_id"] == str(match_id)


def test_notification_archive_and_audit_routes_return_safe_shapes(
    business_context,
) -> None:
    client, services = business_context
    task_id = uuid4()
    archive_id = uuid4()
    conflict_id = uuid4()
    notification_id = uuid4()
    operation_log_id = uuid4()
    services["planning"].resolve_conflict.return_value = SimpleNamespace(
        conflict_id=conflict_id,
        conflict_type="work_hour",
        employee_no="E-ACTOR",
        task_id=task_id,
        related_task_id=None,
        node_id=None,
        dedupe_key="work_hour:E-ACTOR:task:-:-",
        severity="medium",
        description="Capacity is tight",
        suggestion="Review workload",
        status="acknowledged",
        resolved_by_employee_no="E-ACTOR",
        resolution_note="Reviewed",
        detected_at=NOW,
        resolved_at=NOW,
    )
    services["notifications"].list_notifications.return_value = [
        SimpleNamespace(
            notification_id=notification_id,
            reminder_rule_id=None,
            task_id=task_id,
            issue_id=None,
            recipient_employee_no="E-ACTOR",
            channel="in_app",
            title="Due Today",
            content="Task reminder",
            send_status="sent",
            wecom_message_id="fake-wecom:E-ACTOR:1",
            fail_reason=None,
            retry_count=0,
            retry_next_at=None,
            sent_at=NOW,
            read_at=None,
            dedupe_key="task:1:due_today",
            created_at=NOW,
        )
    ]
    services["archive"].archive_task.return_value = SimpleNamespace(
        archive_id=archive_id,
        task_id=task_id,
        archive_snapshot={"task": {"task_name": "Task"}},
        source_status_snapshot="completed",
        summary="Task",
        search_keywords=["task"],
        review_result="approved",
        risk_points=[],
        reusable_template={"nodes": []},
        actual_hours_total=Decimal("8"),
        archived_by_employee_no="E-ACTOR",
        archived_at=NOW,
    )
    services["audit"].list_logs.return_value = {
        "items": [
            SimpleNamespace(
                operation_log_id=operation_log_id,
                request_id="request-id",
                operator_employee_no="E-ACTOR",
                action="archive",
                object_type="task",
                object_id=str(task_id),
                before_data={"status": "completed"},
                after_data={"status": "archived"},
                ip_address=None,
                user_agent=None,
                result="success",
                error_message=None,
                created_at=NOW,
            )
        ],
        "limit": 10,
        "offset": 0,
        "total": 1,
    }

    notifications = client.get(
        "/api/v1/notifications?unread_only=true",
        headers={"X-Employee-No": "E-ACTOR"},
    )
    acknowledged = client.post(
        f"/api/v1/conflicts/{conflict_id}/actions/acknowledge",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"resolution_note": "Reviewed"},
    )
    archive = client.post(
        f"/api/v1/tasks/{task_id}/archive-snapshot",
        headers={"X-Employee-No": "E-ACTOR"},
        json={"search_keywords": ["task"], "review_result": "approved"},
    )
    logs = client.get(
        "/api/v1/operation-logs?limit=10",
        headers={"X-Employee-No": "E-ACTOR"},
    )

    assert [
        notifications.status_code,
        acknowledged.status_code,
        archive.status_code,
        logs.status_code,
    ] == [
        200,
        200,
        201,
        200,
    ]
    assert notifications.json()[0]["notification_id"] == str(notification_id)
    assert acknowledged.json()["status"] == "acknowledged"
    assert logs.json()["items"][0]["operation_log_id"] == str(operation_log_id)
    services["planning"].resolve_conflict.assert_called_once_with(
        "E-ACTOR",
        conflict_id,
        resolution_note="Reviewed",
        status="acknowledged",
    )
    services["notifications"].list_notifications.assert_called_once_with(
        "E-ACTOR", unread_only=True
    )
    services["archive"].archive_task.assert_called_once_with(
        "E-ACTOR",
        task_id,
        summary=None,
        search_keywords=["task"],
        review_result="approved",
        risk_points=[],
    )
    services["audit"].list_logs.assert_called_once_with(
        "E-ACTOR", object_type=None, object_id=None, limit=10, offset=0
    )
