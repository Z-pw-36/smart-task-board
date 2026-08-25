from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.models import (
    AIExtractionRecord,
    EmployeeProfile,
    Notification,
    OperationLog,
    PerformanceMetric,
    ReminderRule,
    Task,
    TaskArchive,
    TaskConflict,
    TaskInput,
    TaskParticipant,
    TaskPerformanceMatch,
    User,
    UserAuthorizedScope,
    WorkloadSnapshot,
)
from app.services import business_capabilities as business_module
from app.services.business_capabilities import (
    ArchiveReuseService,
    FakeASRProvider,
    FakeTaskExtractionProvider,
    PerformanceMetricService,
    PermissionScopeService,
    PlanningAnalyticsService,
    ReminderNotificationService,
    SystemParameterService,
    TaskIntakeService,
)
from app.services.errors import PermissionDeniedError

NOW = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)


class ScalarRows:
    def __init__(self, rows: Iterable[object]) -> None:
        self._rows = list(rows)

    def all(self) -> list[object]:
        return self._rows


class ExecuteRows:
    def __init__(self, rows: Iterable[object]) -> None:
        self._rows = list(rows)

    def all(self) -> list[object]:
        return self._rows

    def scalars(self) -> ScalarRows:
        return ScalarRows(self._rows)

    def scalar_one(self) -> object:
        return self._rows[0]

    def scalar_one_or_none(self) -> object | None:
        return self._rows[0] if self._rows else None


class RecordingSession:
    def __init__(
        self,
        *,
        objects: dict[tuple[type[object], object], object] | None = None,
        scalar_results: list[object] | None = None,
        scalars_results: list[list[object]] | None = None,
        execute_results: list[list[object]] | None = None,
    ) -> None:
        self.objects = objects or {}
        self.scalar_results = list(scalar_results or [])
        self.scalars_results = list(scalars_results or [])
        self.execute_results = list(execute_results or [])
        self.added: list[object] = []
        self.commits = 0
        self.flushes = 0

    def get(self, model: type[object], key: object) -> object | None:
        return self.objects.get((model, key))

    def add(self, row: object) -> None:
        self.added.append(row)

    def flush(self) -> None:
        self.flushes += 1
        for row in self.added:
            for field in (
                "parameter_id",
                "authorized_scope_id",
                "metric_id",
                "performance_match_id",
                "workload_snapshot_id",
                "priority_score_id",
                "conflict_id",
                "reminder_rule_id",
                "notification_id",
                "archive_id",
                "operation_log_id",
            ):
                if hasattr(row, field) and getattr(row, field) is None:
                    setattr(row, field, uuid4())

    def commit(self) -> None:
        self.commits += 1

    def scalar(self, _statement) -> object | None:
        return self.scalar_results.pop(0) if self.scalar_results else None

    def scalars(self, _statement) -> ScalarRows:
        return ScalarRows(self.scalars_results.pop(0) if self.scalars_results else [])

    def execute(self, _statement) -> ExecuteRows:
        return ExecuteRows(self.execute_results.pop(0) if self.execute_results else [])


def _user(employee_no: str, *, role: str = "employee", department_id: UUID | None = None) -> User:
    return User(
        employee_no=employee_no,
        name=employee_no,
        role_type=role,
        status="active",
        department_id=department_id,
    )


def _task(
    *,
    task_id: UUID | None = None,
    creator: str = "CREATOR",
    assignee: str = "ASSIGNEE",
    status: str = "in_progress",
    deadline: datetime | None = None,
    task_weight: int = 3,
) -> Task:
    return Task(
        task_id=task_id or uuid4(),
        task_name="Revenue launch task",
        task_description="Launch revenue dashboard and KPI deliverable",
        task_goal="Improve revenue reporting",
        creator_employee_no=creator,
        main_assignee_employee_no=assignee,
        reviewer_employee_no="REVIEWER",
        report_to_level="director",
        status=status,
        deadline=deadline,
        estimated_hours=Decimal("16"),
        actual_hours=Decimal("4"),
        task_weight=task_weight,
        deliverable="Revenue dashboard",
        acceptance_criteria="KPI is measurable",
        is_urgent=deadline is not None and deadline <= NOW + timedelta(days=1),
        task_version=3,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(hours=1),
    )


def _operation_logs(session: RecordingSession) -> list[OperationLog]:
    return [row for row in session.added if isinstance(row, OperationLog)]


def test_system_parameter_upsert_validates_admin_type_and_writes_audit() -> None:
    admin = _user("ADMIN", role="admin")
    session = RecordingSession(objects={(User, "ADMIN"): admin}, scalar_results=[None])

    row = SystemParameterService(session, clock=lambda: NOW).upsert_parameter(
        "ADMIN",
        "priority_boost",
        value="25",
        param_type="number",
        module="priority",
        name="Priority boost",
    )

    assert row.param_key == "priority_boost"
    assert row.param_value == "25"
    assert row.updated_by_employee_no == "ADMIN"
    assert _operation_logs(session)[0].action == "parameter_changed"
    assert session.commits == 1


def test_permission_scope_grant_and_recommendation_are_admin_scoped() -> None:
    department_id = uuid4()
    admin = _user("ADMIN", role="admin")
    target = _user("TARGET", department_id=department_id)
    candidate = _user("CANDIDATE", department_id=department_id)
    profile = EmployeeProfile(
        employee_no="CANDIDATE",
        responsibility_text="Revenue dashboard automation",
        skill_tags=["python", "kpi"],
        availability_status="available",
        daily_capacity_hours=Decimal("8"),
        standard_task_count=5,
        standard_task_weight=3,
        emergency_tolerance_count=2,
    )
    session = RecordingSession(
        objects={(User, "ADMIN"): admin, (User, "TARGET"): target, (User, "CANDIDATE"): candidate},
        execute_results=[[(candidate, profile)]],
    )
    service = PermissionScopeService(session, clock=lambda: NOW)

    scope = service.grant_scope(
        "ADMIN",
        employee_no="TARGET",
        scope_type="department",
        scope_id=str(department_id),
        permission_type="view",
        valid_from=NOW,
        valid_to=NOW + timedelta(days=1),
    )
    recommendations = service.recommend_assignees(
        "ADMIN",
        task_description="Need python KPI dashboard",
        required_skill_tags=["kpi"],
        department_id=department_id,
        limit=3,
    )

    assert isinstance(scope, UserAuthorizedScope)
    assert scope.created_by_employee_no == "ADMIN"
    assert recommendations[0]["employee_no"] == "CANDIDATE"
    assert recommendations[0]["score"] > 0
    assert {log.action for log in _operation_logs(session)} == {"permission_scope_granted"}


def test_task_intake_voice_clarify_and_confirm_create_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = _user("CREATOR")
    input_id = uuid4()
    session = RecordingSession(objects={(User, "CREATOR"): actor, (TaskInput, input_id): None})
    class FailingDecompositionProvider:
        def decompose(self, _extracted):
            raise AssertionError("task creation must not trigger decomposition")

    service = TaskIntakeService(
        session,
        object,
        asr_provider=FakeASRProvider(),
        extraction_provider=FakeTaskExtractionProvider(),
        decomposition_provider=FailingDecompositionProvider(),
        clock=lambda: NOW,
    )

    result = service.submit_input(
        "CREATOR",
        input_id=input_id,
        input_type="voice",
        raw_text=None,
        voice_file_url="https://example.invalid/audio.wav",
        source_channel="wecom",
    )

    assert result.task_input.asr_text == "Transcribed voice input from https://example.invalid/audio.wav"
    assert "main_assignee_employee_no" in result.extraction.missing_fields
    assert _operation_logs(session)[0].action == "task_input_submitted"

    previous = result.extraction
    session.objects[(TaskInput, input_id)] = result.task_input
    session.scalar_results = [previous]
    clarified = service.clarify(
        "CREATOR",
        input_id,
        {
            "main_assignee_employee_no": "ASSIGNEE",
            "report_to_employee_no": "REVIEWER",
            "deadline": "2026-08-30T09:00:00+00:00",
            "estimated_hours": "8",
            "performance_metric": "Revenue dashboard KPI",
            "acceptance_criteria": "Reviewed output",
        },
    )
    assert clarified.extraction.missing_fields == []
    assert clarified.extraction.confirmed_at == NOW

    department_id = uuid4()
    captured: dict[str, object] = {}

    class CapturingWorkflow:
        def __init__(self, _uow_factory, *, clock) -> None:
            self.clock = clock

        def create_task_draft(self, command):
            captured["command"] = command
            return Task(
                task_id=command.task_id,
                task_name=command.task_name,
                creator_employee_no=command.creator_employee_no,
                main_assignee_employee_no=command.main_assignee_employee_no,
                status="draft",
                task_version=1,
                created_at=NOW,
                updated_at=NOW,
            )

    monkeypatch.setattr(business_module, "TaskWorkflowService", CapturingWorkflow)
    session.objects[(AIExtractionRecord, clarified.extraction.extraction_id)] = clarified.extraction
    session.scalar_results = []
    task = service.create_draft_from_extraction(
        "CREATOR",
        extraction_id=clarified.extraction.extraction_id,
        corrections={"task_name": "Confirmed task", "department_id": str(department_id)},
        task_id=uuid4(),
    )

    command = captured["command"]
    assert task.status == "draft"
    assert command.operation_source == "ai_intake"
    assert command.task_name == "Confirmed task"
    assert command.department_id == department_id
    assert command.nodes == ()
    assert command.dependencies == ()
    assert command.node_participants == ()
    assert command.extraction_record_ids == (clarified.extraction.extraction_id,)


def test_main_assignee_suggests_task_plan_after_acceptance_and_sanitizes_owner() -> None:
    task_id = uuid4()
    task = _task(task_id=task_id, status="in_progress", deadline=NOW + timedelta(days=5))
    extraction = AIExtractionRecord(
        extraction_id=uuid4(),
        input_id=uuid4(),
        task_id=task_id,
        extracted_json={"nodes": [{"clientNodeId": "from-extraction", "nodeName": "Old node"}]},
        missing_fields=[],
        low_confidence_fields=[],
        confirm_questions=[],
        confirmed_at=NOW,
    )
    participant = TaskParticipant(
        task_id=task_id,
        employee_no="COLLAB",
        participant_role="collaborator",
        is_primary=False,
    )

    class PlanningProvider:
        def decompose(self, extracted):
            assert extracted["task_id"] == str(task_id)
            assert extracted["planning_instructions"] == "make it execution ready"
            return {
                "nodes": [
                    {
                        "clientNodeId": "draft-node-1",
                        "nodeName": "Prepare scope",
                        "actionDetail": "Confirm input scope.",
                        "ownerEmployeeNo": "OUTSIDER",
                        "plannedDeadline": (NOW + timedelta(days=1)).isoformat(),
                        "deliverable": "Scope note",
                        "acceptanceCriteria": "Scope is approved",
                    },
                    {
                        "clientNodeId": "draft-node-2",
                        "nodeName": "Deliver result",
                        "ownerEmployeeNo": "COLLAB",
                        "plannedDeadline": (NOW + timedelta(days=4)).isoformat(),
                        "dependencies": ["draft-node-1"],
                    },
                ],
                "dependencies": [
                    {
                        "predecessorClientNodeId": "draft-node-1",
                        "successorClientNodeId": "draft-node-2",
                        "dependencyType": "finish_to_start",
                    }
                ],
            }

    session = RecordingSession(
        objects={
            (Task, task_id): task,
            (User, "ASSIGNEE"): _user("ASSIGNEE"),
            (User, "OUTSIDER"): _user("OUTSIDER"),
        },
        scalar_results=[extraction],
        scalars_results=[[participant], [participant]],
    )
    service = TaskIntakeService(
        session,
        object,
        decomposition_provider=PlanningProvider(),
        clock=lambda: NOW,
    )

    with pytest.raises(PermissionDeniedError):
        service.suggest_task_plan("CREATOR", task_id)

    response = service.suggest_task_plan(
        "ASSIGNEE",
        task_id,
        instructions=" make it execution ready ",
    )

    assert response["task_id"] == task_id
    assert len(response["suggested_nodes"]) == 2
    assert response["suggested_nodes"][0]["suggested_owner_employee_no"] is None
    assert response["suggested_nodes"][1]["suggested_owner_employee_no"] == "COLLAB"
    assert response["suggested_dependencies"] == [
        {
            "predecessor_client_node_id": "draft-node-1",
            "successor_client_node_id": "draft-node-2",
            "dependency_type": "finish_to_start",
            "reason": None,
        }
    ]


def test_performance_metric_suggestion_and_confirmation_are_explainable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task()
    metric = PerformanceMetric(
        metric_id=uuid4(),
        metric_type="revenue dashboard",
        metric_name="Revenue dashboard KPI",
        business_unit="sales",
        definition_formula="dashboard completion rate",
        deliverable="Revenue dashboard",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    session = RecordingSession(
        objects={(User, "MANAGER"): _user("MANAGER", role="manager"), (Task, task.task_id): task},
        scalar_results=[None],
        scalars_results=[[metric]],
    )
    monkeypatch.setattr(
        business_module.PermissionScopeService,
        "assert_can_view_task",
        lambda _self, _actor, _task_id: task,
    )

    service = PerformanceMetricService(session, clock=lambda: NOW)
    created = service.create_metric(
        "MANAGER",
        {
            "metric_type": "quality",
            "metric_name": "Release quality",
            "status": "active",
        },
    )
    matches = service.suggest_matches("MANAGER", task.task_id, limit=1)
    match = matches[0]
    session.objects[(TaskPerformanceMatch, match.performance_match_id)] = match
    confirmed = service.confirm_match("MANAGER", task.task_id, match.performance_match_id)

    assert created.metric_name == "Release quality"
    assert match.match_reason.endswith("deterministic token overlap")
    assert confirmed.is_confirmed is True
    assert confirmed.confirmed_by_employee_no == "MANAGER"
    expected_actions = {
        "performance_metric_created",
        "performance_matches_suggested",
        "kpi_match_confirmed",
    }
    assert expected_actions <= {log.action for log in _operation_logs(session)}


def test_planning_workload_priorities_and_conflict_dedupe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedParameterService:
        def __init__(self, _session) -> None:
            pass

        def snapshot(self, _keys=None) -> dict[str, object]:
            return {
                "daily_capacity_hours": Decimal("4"),
                "standard_task_count": Decimal("1"),
                "standard_task_weight": Decimal("2"),
                "emergency_tolerance_count": Decimal("1"),
                "importance_threshold": Decimal("60"),
                "urgency_threshold": Decimal("60"),
            }

    monkeypatch.setattr(business_module, "SystemParameterService", FixedParameterService)
    target = _user("ASSIGNEE")
    active = _task(assignee="ASSIGNEE", deadline=NOW - timedelta(hours=2), task_weight=5)
    profile = EmployeeProfile(
        employee_no="ASSIGNEE",
        daily_capacity_hours=Decimal("4"),
        standard_task_count=1,
        standard_task_weight=2,
        emergency_tolerance_count=1,
        availability_status="available",
    )
    session = RecordingSession(
        objects={(User, "ASSIGNEE"): target, (EmployeeProfile, "ASSIGNEE"): profile}
    )
    service = PlanningAnalyticsService(session, clock=lambda: NOW)
    monkeypatch.setattr(service, "_active_tasks_for_employee", lambda _employee: [active])
    monkeypatch.setattr(service, "_blocked_count", lambda _employee, _tasks: 1)
    monkeypatch.setattr(service, "_visible_active_tasks", lambda _actor: [active])
    monkeypatch.setattr(service, "_confirmed_performance_score", lambda _task_id: Decimal("100"))

    workload = service.calculate_workload(
        "ASSIGNEE",
        "ASSIGNEE",
        NOW,
        NOW + timedelta(days=1),
    )
    priorities = service.calculate_priorities("ASSIGNEE")

    existing = TaskConflict(
        conflict_id=uuid4(),
        conflict_type="work_hour",
        employee_no="ASSIGNEE",
        task_id=active.task_id,
        dedupe_key=f"work_hour:ASSIGNEE:{active.task_id}:-:-",
        severity="medium",
        description="old",
        status="resolved",
        detected_at=NOW - timedelta(days=1),
        resolved_by_employee_no="ASSIGNEE",
        resolved_at=NOW - timedelta(hours=1),
        resolution_note="old",
    )
    session.scalar_results = [existing]
    conflict = TaskConflict(
        conflict_type="work_hour",
        employee_no="ASSIGNEE",
        task_id=active.task_id,
        dedupe_key=existing.dedupe_key,
        severity="high",
        description="new",
        suggestion="adjust",
        status="open",
        detected_at=NOW,
    )
    monkeypatch.setattr(service, "_detect_work_hour", lambda _employee, _now: [conflict])
    monkeypatch.setattr(service, "_detect_deadline_concentration", lambda _employee, _now: [])
    monkeypatch.setattr(service, "_detect_dependency_conflicts", lambda _employee, _now: [])
    monkeypatch.setattr(service, "_detect_emergency_displacement", lambda _employee, _now: [])
    conflicts = service.detect_conflicts("ASSIGNEE")

    assert isinstance(workload, WorkloadSnapshot)
    assert workload.workload_level in {"busy", "overloaded"}
    assert priorities[0].priority_quadrant == "important_urgent"
    assert conflicts == [existing]
    assert existing.status == "open"
    assert existing.resolved_by_employee_no is None
    assert session.commits == 3


def test_conflict_acknowledge_records_actor_and_audit() -> None:
    conflict_id = uuid4()
    conflict = TaskConflict(
        conflict_id=conflict_id,
        conflict_type="work_hour",
        employee_no="ASSIGNEE",
        task_id=uuid4(),
        dedupe_key="work_hour:ASSIGNEE:task:-:-",
        severity="medium",
        description="Capacity is tight",
        suggestion="Review workload",
        status="open",
        detected_at=NOW,
    )
    session = RecordingSession(objects={(TaskConflict, conflict_id): conflict})

    result = PlanningAnalyticsService(session, clock=lambda: NOW).resolve_conflict(
        "ASSIGNEE",
        conflict_id,
        resolution_note="Reviewed with owner",
        status="acknowledged",
    )

    assert result.status == "acknowledged"
    assert result.resolved_by_employee_no == "ASSIGNEE"
    assert result.resolved_at == NOW
    assert _operation_logs(session)[0].action == "conflict_acknowledged"
    assert session.commits == 1


def test_reminder_notification_dedupe_retry_and_read_state() -> None:
    rule = ReminderRule(
        reminder_rule_id=uuid4(),
        task_id=uuid4(),
        reminder_type="overdue",
        recipient_employee_no="ASSIGNEE",
        next_trigger_at=NOW,
        repeat_rule="daily",
        dedupe_key="task:1:overdue",
        is_active=True,
        created_at=NOW,
    )
    session = RecordingSession(
        objects={(User, "MANAGER"): _user("MANAGER", role="manager")},
        scalars_results=[[rule]],
    )
    service = ReminderNotificationService(session, clock=lambda: NOW)
    notifications = service.create_due_notifications("MANAGER")

    notification = next(row for row in session.added if isinstance(row, Notification))
    assert notifications == [notification]
    assert notification.dedupe_key == f"task:1:overdue:{NOW.isoformat()}"
    assert rule.last_triggered_at == NOW
    assert rule.next_trigger_at == datetime(2026, 8, 22, 9, 0, tzinfo=UTC)

    class FailingProvider:
        def send(self, _recipient: str, _title: str, _content: str) -> str:
            raise RuntimeError("temporary channel failure")

    session.scalars_results = [[notification]]
    service = ReminderNotificationService(session, provider=FailingProvider(), clock=lambda: NOW)
    sent = service.send_pending("MANAGER")
    assert sent == [notification]
    assert notification.send_status == "failed"
    assert notification.retry_count == 1
    assert notification.retry_next_at == NOW + timedelta(minutes=5)

    session.objects[(Notification, notification.notification_id)] = notification
    marked = service.mark_read("ASSIGNEE", notification.notification_id)
    assert marked.read_at == NOW
    assert session.commits == 3


def test_archive_snapshot_is_immutable_and_reusable(monkeypatch: pytest.MonkeyPatch) -> None:
    task = _task(creator="CREATOR", status="completed")

    class FixedPermissionService:
        def __init__(self, _session, *, clock=None) -> None:
            pass

        def assert_can_view_task(self, _actor: str, _task_id: UUID) -> Task:
            return task

    monkeypatch.setattr(business_module, "PermissionScopeService", FixedPermissionService)
    session = RecordingSession(
        objects={(User, "CREATOR"): _user("CREATOR"), (TaskArchive, uuid4()): None},
        scalar_results=[None],
    )
    service = ArchiveReuseService(session, object, clock=lambda: NOW)
    monkeypatch.setattr(
        service,
        "_snapshot",
        lambda _task: {"task": {"task_name": "Revenue launch"}},
    )
    monkeypatch.setattr(service, "_template", lambda _snapshot: {"nodes": [], "dependencies": []})
    monkeypatch.setattr(service, "_actual_hours_total", lambda _task_id: Decimal("12"))

    archive = service.archive_task(
        "CREATOR",
        task.task_id,
        summary=None,
        search_keywords=["revenue", "dashboard"],
        review_result="approved",
        risk_points=["late input"],
    )

    assert isinstance(archive, TaskArchive)
    assert archive.archive_snapshot == {"task": {"task_name": "Revenue launch"}}
    assert archive.actual_hours_total == Decimal("12")
    assert task.status == "archived"
    assert task.task_version == 4
    assert _operation_logs(session)[0].action == "archive"
