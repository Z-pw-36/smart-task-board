from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, delete, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api import dependencies
from app.api.v1 import tasks as task_routes
from app.db.unit_of_work import UnitOfWork
from app.main import app
from app.models import (
    AIExtractionRecord,
    Department,
    Task,
    TaskInput,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskStatusLog,
    User,
)
from app.repositories import TaskNodeRepository, TaskStatusLogRepository

pytestmark = pytest.mark.postgresql

EXPECTED_DATABASE = "smarttaskboard_core_test"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 46479
EXPECTED_REVISION = "17f69ea12754"
EXPECTED_TABLES = {
    "ai_extraction_records",
    "departments",
    "task_inputs",
    "task_node_dependencies",
    "task_node_participants",
    "task_nodes",
    "task_participants",
    "task_status_logs",
    "tasks",
    "users",
}


@dataclass
class Phase5Records:
    department_ids: set[UUID] = field(default_factory=set)
    employee_nos: set[str] = field(default_factory=set)
    input_ids: set[UUID] = field(default_factory=set)
    extraction_ids: set[UUID] = field(default_factory=set)
    task_ids: set[UUID] = field(default_factory=set)


@dataclass(frozen=True)
class ApiReferences:
    department_id: UUID
    creator: str
    assignee: str
    reviewer: str
    reporter: str
    participant: str
    node_participant: str
    outsider: str
    input_id: UUID
    extraction_id: UUID


@pytest.fixture(scope="session")
def phase5_engine() -> Iterator[Engine]:
    if os.getenv("RUN_POSTGRESQL_INTEGRATION") != "1":
        pytest.skip("set RUN_POSTGRESQL_INTEGRATION=1 for explicit PostgreSQL tests")
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")
    parsed = make_url(database_url)
    if (
        parsed.drivername != "postgresql+psycopg"
        or parsed.host != EXPECTED_HOST
        or parsed.port != EXPECTED_PORT
        or parsed.database != EXPECTED_DATABASE
    ):
        pytest.fail("Phase 5 target is not the approved isolated database")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c statement_timeout=5000 -c lock_timeout=1000"},
    )
    try:
        tables = set(inspect(engine).get_table_names(schema="public"))
        assert tables - {"alembic_version"} == EXPECTED_TABLES
        with engine.connect() as connection:
            revisions = connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalars().all()
        assert revisions == [EXPECTED_REVISION]
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def phase5_session_factory(
    phase5_engine: Engine,
) -> sessionmaker[Session]:
    return sessionmaker(
        bind=phase5_engine,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture
def phase5_records(phase5_engine: Engine) -> Iterator[Phase5Records]:
    records = Phase5Records()
    yield records
    with phase5_engine.begin() as connection:
        task_ids = records.task_ids
        if task_ids:
            connection.execute(
                delete(TaskStatusLog).where(TaskStatusLog.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskNodeDependency).where(TaskNodeDependency.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskNodeParticipant).where(TaskNodeParticipant.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskParticipant).where(TaskParticipant.task_id.in_(task_ids))
            )
            connection.execute(delete(TaskNode).where(TaskNode.task_id.in_(task_ids)))
        if records.extraction_ids:
            connection.execute(
                delete(AIExtractionRecord).where(
                    AIExtractionRecord.extraction_id.in_(records.extraction_ids)
                )
            )
        if task_ids:
            connection.execute(delete(Task).where(Task.task_id.in_(task_ids)))
        if records.input_ids:
            connection.execute(
                delete(TaskInput).where(TaskInput.input_id.in_(records.input_ids))
            )
        if records.employee_nos:
            connection.execute(delete(User).where(User.employee_no.in_(records.employee_nos)))
        if records.department_ids:
            connection.execute(
                delete(Department).where(
                    Department.department_id.in_(records.department_ids)
                )
            )


def _employee_no(label: str) -> str:
    return f"P5-{label}-{uuid4().hex[:12]}"


def _create_references(
    factory: sessionmaker[Session],
    records: Phase5Records,
) -> ApiReferences:
    department_id = uuid4()
    employees = {label: _employee_no(label) for label in (
        "creator",
        "assignee",
        "reviewer",
        "reporter",
        "participant",
        "node-participant",
        "outsider",
    )}
    input_id, extraction_id = uuid4(), uuid4()
    records.department_ids.add(department_id)
    records.employee_nos.update(employees.values())
    records.input_ids.add(input_id)
    records.extraction_ids.add(extraction_id)

    with factory.begin() as session:
        session.add(
            Department(
                department_id=department_id,
                department_name="Phase 5 API Integration",
                department_type="team",
                department_path=f"/{department_id}",
                status="active",
            )
        )
        session.add_all(
            [
                User(
                    employee_no=employee_no,
                    name=employee_no,
                    department_id=department_id,
                    role_type="employee",
                    status="active",
                )
                for employee_no in employees.values()
            ]
        )
        session.add(
            TaskInput(
                input_id=input_id,
                input_type="text",
                raw_text="Phase 5 HTTP workflow",
                source_channel="phase5-api-integration",
                submitted_by_employee_no=employees["creator"],
            )
        )
        session.add(
            AIExtractionRecord(
                extraction_id=extraction_id,
                input_id=input_id,
                extracted_json={"task_name": "Phase 5 HTTP workflow"},
                missing_fields=[],
                low_confidence_fields=[],
                confirm_questions=[],
            )
        )
    return ApiReferences(
        department_id=department_id,
        creator=employees["creator"],
        assignee=employees["assignee"],
        reviewer=employees["reviewer"],
        reporter=employees["reporter"],
        participant=employees["participant"],
        node_participant=employees["node-participant"],
        outsider=employees["outsider"],
        input_id=input_id,
        extraction_id=extraction_id,
    )


@pytest.fixture
def phase5_client(
    phase5_session_factory: sessionmaker[Session],
) -> Iterator[TestClient]:
    def override_uow_factory():
        return lambda: UnitOfWork(phase5_session_factory)

    def override_get_db() -> Iterator[Session]:
        session = phase5_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[dependencies.get_uow_factory] = override_uow_factory
    app.dependency_overrides[dependencies.get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _headers(employee_no: str) -> dict[str, str]:
    return {"X-Employee-No": employee_no}


def _create_payload(refs: ApiReferences) -> tuple[dict[str, object], UUID, UUID]:
    first, second = uuid4(), uuid4()
    return (
        {
            "task_name": "Phase 5 API Core Workflow",
            "main_assignee_employee_no": refs.assignee,
            "report_to_employee_no": refs.reporter,
            "reviewer_employee_no": refs.reviewer,
            "department_id": str(refs.department_id),
            "acceptance_criteria": "Both nodes completed",
            "participants": [
                {
                    "employee_no": refs.participant,
                    "participant_role": "collaborator",
                }
            ],
            "nodes": [
                {
                    "node_id": str(first),
                    "node_order": 1,
                    "node_name": "Prepare",
                    "owner_employee_no": refs.assignee,
                },
                {
                    "node_id": str(second),
                    "node_order": 2,
                    "node_name": "Deliver",
                    "owner_employee_no": refs.assignee,
                },
            ],
            "dependencies": [
                {
                    "predecessor_node_id": str(first),
                    "successor_node_id": str(second),
                }
            ],
            "node_participants": [
                {
                    "node_id": str(first),
                    "employee_no": refs.node_participant,
                    "participant_role": "collaborator",
                }
            ],
            "extraction_record_ids": [str(refs.extraction_id)],
        },
        first,
        second,
    )


def _post_action(
    client: TestClient,
    task_id: UUID,
    action: str,
    employee_no: str,
    version: int,
):
    return client.post(
        f"/api/v1/tasks/{task_id}/actions/{action}",
        headers=_headers(employee_no),
        json={"expected_task_version": version},
    )


def test_http_core_workflow_and_read_permissions(
    phase5_client: TestClient,
    phase5_session_factory: sessionmaker[Session],
    phase5_records: Phase5Records,
) -> None:
    refs = _create_references(phase5_session_factory, phase5_records)
    payload, first, second = _create_payload(refs)

    missing_header = phase5_client.post("/api/v1/tasks", json=payload)
    blank_header = phase5_client.post(
        "/api/v1/tasks",
        headers={"X-Employee-No": "   "},
        json=payload,
    )
    assert (missing_header.status_code, blank_header.status_code) == (401, 401)

    created = phase5_client.post(
        "/api/v1/tasks",
        headers=_headers(refs.creator),
        json=payload,
    )
    assert created.status_code == 201
    assert (created.json()["status"], created.json()["task_version"]) == ("draft", 1)
    task_id = UUID(created.json()["task_id"])
    phase5_records.task_ids.add(task_id)

    old_version = _post_action(
        phase5_client,
        task_id,
        "submit-for-confirmation",
        refs.creator,
        99,
    )
    invalid_state = _post_action(
        phase5_client,
        task_id,
        "confirm-and-send",
        refs.creator,
        1,
    )
    assert old_version.status_code == 409
    assert old_version.json()["error"]["code"] == "task_version_conflict"
    assert invalid_state.status_code == 409
    assert invalid_state.json()["error"]["code"] == "invalid_state_transition"

    invalid_request = _post_action(
        phase5_client,
        task_id,
        "submit-for-confirmation",
        refs.creator,
        0,
    )
    blank_reason = phase5_client.post(
        f"/api/v1/tasks/{task_id}/actions/return",
        headers=_headers(refs.assignee),
        json={"expected_task_version": 1, "reason": "  "},
    )
    assert invalid_request.status_code == 422
    assert invalid_request.json()["error"]["code"] == "request_validation_error"
    assert blank_reason.status_code == 422

    submitted = _post_action(
        phase5_client,
        task_id,
        "submit-for-confirmation",
        refs.creator,
        1,
    )
    sent = _post_action(
        phase5_client,
        task_id,
        "confirm-and-send",
        refs.creator,
        2,
    )
    accepted = _post_action(
        phase5_client,
        task_id,
        "accept",
        refs.assignee,
        3,
    )
    assert [item.status_code for item in (submitted, sent, accepted)] == [200, 200, 200]
    assert (submitted.json()["status"], submitted.json()["task_version"]) == (
        "pending_confirmation",
        2,
    )
    assert (sent.json()["status"], sent.json()["task_version"]) == (
        "pending_acceptance",
        3,
    )
    assert (accepted.json()["status"], accepted.json()["task_version"]) == (
        "in_progress",
        4,
    )

    dependency_blocked = phase5_client.post(
        f"/api/v1/tasks/{task_id}/nodes/{second}/actions/start",
        headers=_headers(refs.assignee),
        json={"expected_task_version": 4},
    )
    participant_denied = phase5_client.post(
        f"/api/v1/tasks/{task_id}/nodes/{first}/actions/start",
        headers=_headers(refs.node_participant),
        json={"expected_task_version": 4},
    )
    assert dependency_blocked.status_code == 409
    assert dependency_blocked.json()["error"]["code"] == "dependency_not_satisfied"
    assert participant_denied.status_code == 403
    assert participant_denied.json()["error"]["code"] == "permission_denied"

    node1_started = phase5_client.post(
        f"/api/v1/tasks/{task_id}/nodes/{first}/actions/start",
        headers=_headers(refs.assignee),
        json={"expected_task_version": 4},
    )
    node1_progress = phase5_client.patch(
        f"/api/v1/tasks/{task_id}/nodes/{first}/progress",
        headers=_headers(refs.assignee),
        json={
            "expected_task_version": 5,
            "progress_percent": 60,
            "actual_hours": "1.5",
        },
    )
    node1_completed = phase5_client.post(
        f"/api/v1/tasks/{task_id}/nodes/{first}/actions/complete",
        headers=_headers(refs.assignee),
        json={"expected_task_version": 6},
    )
    node2_started = phase5_client.post(
        f"/api/v1/tasks/{task_id}/nodes/{second}/actions/start",
        headers=_headers(refs.assignee),
        json={"expected_task_version": 7},
    )
    node2_completed = phase5_client.post(
        f"/api/v1/tasks/{task_id}/nodes/{second}/actions/complete",
        headers=_headers(refs.assignee),
        json={"expected_task_version": 8},
    )
    assert [
        item.json()["task_version"]
        for item in (
            node1_started,
            node1_progress,
            node1_completed,
            node2_started,
            node2_completed,
        )
    ] == [5, 6, 7, 8, 9]

    completion = _post_action(
        phase5_client,
        task_id,
        "submit-completion",
        refs.assignee,
        9,
    )
    approved = _post_action(
        phase5_client,
        task_id,
        "approve-completion",
        refs.reviewer,
        10,
    )
    assert (completion.json()["status"], completion.json()["task_version"]) == (
        "pending_review",
        10,
    )
    assert (approved.json()["status"], approved.json()["task_version"]) == (
        "completed",
        11,
    )

    completed_rejected = phase5_client.post(
        f"/api/v1/tasks/{task_id}/nodes/{first}/actions/start",
        headers=_headers(refs.assignee),
        json={"expected_task_version": 11},
    )
    assert completed_rejected.status_code == 409
    assert completed_rejected.json()["error"]["code"] == "invalid_state_transition"

    for reader in (
        refs.creator,
        refs.assignee,
        refs.reviewer,
        refs.reporter,
        refs.participant,
        refs.node_participant,
    ):
        response = phase5_client.get(
            f"/api/v1/tasks/{task_id}",
            headers=_headers(reader),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
    outsider = phase5_client.get(
        f"/api/v1/tasks/{task_id}",
        headers=_headers(refs.outsider),
    )
    missing = phase5_client.get(
        f"/api/v1/tasks/{uuid4()}",
        headers=_headers(refs.creator),
    )
    assert outsider.status_code == 403
    assert missing.status_code == 404

    nodes = phase5_client.get(
        f"/api/v1/tasks/{task_id}/nodes",
        headers=_headers(refs.creator),
    )
    single_node = phase5_client.get(
        f"/api/v1/tasks/{task_id}/nodes/{first}",
        headers=_headers(refs.creator),
    )
    logs = phase5_client.get(
        f"/api/v1/tasks/{task_id}/status-logs?limit=50&offset=0",
        headers=_headers(refs.creator),
    )
    assert nodes.status_code == single_node.status_code == logs.status_code == 200
    assert [(item["status"], item["progress_percent"]) for item in nodes.json()] == [
        ("completed", 100),
        ("completed", 100),
    ]
    assert logs.json()["total"] == 11
    assert [item["task_version"] for item in logs.json()["items"]] == list(
        range(1, 12)
    )
    assert {item["operation_source"] for item in logs.json()["items"]} == {"rest_api"}

    with phase5_session_factory() as session:
        stored = session.get(Task, task_id)
        assert stored is not None
        assert (stored.status, stored.task_version) == ("completed", 11)
        stored_nodes = TaskNodeRepository(session).list_nodes(task_id)
        assert [(item.status, item.progress_percent) for item in stored_nodes] == [
            ("completed", 100),
            ("completed", 100),
        ]
        stored_logs = TaskStatusLogRepository(session).list_by_task_id(task_id)
        assert len(stored_logs) == 11


def test_http_unique_conflict_is_sanitized_and_rolled_back(
    phase5_client: TestClient,
    phase5_session_factory: sessionmaker[Session],
    phase5_records: Phase5Records,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refs = _create_references(phase5_session_factory, phase5_records)
    payload, _, _ = _create_payload(refs)
    first = phase5_client.post(
        "/api/v1/tasks",
        headers=_headers(refs.creator),
        json=payload,
    )
    assert first.status_code == 201
    task_id = UUID(first.json()["task_id"])
    phase5_records.task_ids.add(task_id)

    original_create_command = task_routes._create_command

    def duplicate_id_command(request, actor):
        return replace(original_create_command(request, actor), task_id=task_id)

    monkeypatch.setattr(task_routes, "_create_command", duplicate_id_command)
    duplicate = phase5_client.post(
        "/api/v1/tasks",
        headers=_headers(refs.creator),
        json=payload,
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "resource_conflict"
    assert "sql" not in duplicate.text.lower()
    assert "password" not in duplicate.text.lower()
    with phase5_session_factory() as session:
        stored = session.get(Task, task_id)
        assert stored is not None and stored.task_version == 1
        logs = session.scalars(
            select(TaskStatusLog).where(TaskStatusLog.task_id == task_id)
        ).all()
        assert len(logs) == 1
