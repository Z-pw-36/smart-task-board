from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, delete, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.unit_of_work import UnitOfWork
from app.models import (
    AIExtractionRecord,
    Department,
    Task,
    TaskCompletionReview,
    TaskInput,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskStatusLog,
    User,
)
from app.repositories import TaskNodeRepository, TaskRepository, TaskStatusLogRepository
from app.services import (
    BusinessValidationError,
    CreateTaskDraftCommand,
    DependencyCycleError,
    DependencyNotSatisfiedError,
    InvalidStateTransitionError,
    PermissionDeniedError,
    TaskNodeDependencyDraft,
    TaskNodeDraft,
    TaskNodeParticipantDraft,
    TaskNodeWorkflowService,
    TaskVersionConflictError,
    TaskWorkflowService,
)

pytestmark = pytest.mark.postgresql

EXPECTED_DATABASE = "smarttaskboard_core_test"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 46479
EXPECTED_REVISION = "c31f8e7a4d02"
EXPECTED_TABLES = {
    "ai_extraction_records",
    "departments",
    "task_inputs",
    "task_node_dependencies",
    "task_node_participants",
    "task_nodes",
    "task_participants",
    "task_completion_reviews",
    "task_progress_reports",
    "task_issues",
    "task_status_logs",
    "tasks",
    "users",
}


@dataclass
class Phase4Records:
    department_ids: set[UUID] = field(default_factory=set)
    employee_nos: set[str] = field(default_factory=set)
    input_ids: set[UUID] = field(default_factory=set)
    extraction_ids: set[UUID] = field(default_factory=set)
    task_ids: set[UUID] = field(default_factory=set)


@dataclass(frozen=True)
class References:
    department_id: UUID
    creator: str
    assignee: str
    reviewer: str
    outsider: str
    input_id: UUID
    extraction_id: UUID


class StepClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 8, 18, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        result = self.current
        self.current += timedelta(seconds=1)
        return result


@pytest.fixture(scope="session")
def phase4_engine() -> Iterator[Engine]:
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
        pytest.fail("Phase 4 target is not the approved isolated database")

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
def phase4_session_factory(
    phase4_engine: Engine,
) -> sessionmaker[Session]:
    return sessionmaker(
        bind=phase4_engine,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture
def phase4_records(phase4_engine: Engine) -> Iterator[Phase4Records]:
    records = Phase4Records()
    yield records
    with phase4_engine.begin() as connection:
        task_ids = records.task_ids
        if task_ids:
            connection.execute(
                delete(TaskStatusLog).where(TaskStatusLog.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskCompletionReview).where(
                    TaskCompletionReview.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskNodeDependency).where(
                    TaskNodeDependency.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskNodeParticipant).where(
                    TaskNodeParticipant.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskParticipant).where(TaskParticipant.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskNode).where(TaskNode.task_id.in_(task_ids))
            )
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
            connection.execute(
                delete(User).where(User.employee_no.in_(records.employee_nos))
            )
        if records.department_ids:
            connection.execute(
                delete(Department).where(
                    Department.department_id.in_(records.department_ids)
                )
            )


def _employee_no(label: str) -> str:
    return f"P4-{label}-{uuid4().hex[:12]}"


def _create_references(
    factory: sessionmaker[Session],
    records: Phase4Records,
) -> References:
    department_id = uuid4()
    creator = _employee_no("creator")
    assignee = _employee_no("assignee")
    reviewer = _employee_no("reviewer")
    outsider = _employee_no("outsider")
    input_id = uuid4()
    extraction_id = uuid4()
    records.department_ids.add(department_id)
    records.employee_nos.update({creator, assignee, reviewer, outsider})
    records.input_ids.add(input_id)
    records.extraction_ids.add(extraction_id)

    with factory.begin() as session:
        session.add(
            Department(
                department_id=department_id,
                department_name="Phase 4 Integration",
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
                for employee_no in (creator, assignee, reviewer, outsider)
            ]
        )
        session.add(
            TaskInput(
                input_id=input_id,
                input_type="text",
                raw_text="Phase 4 workflow",
                source_channel="phase4-integration",
                submitted_by_employee_no=creator,
            )
        )
        session.add(
            AIExtractionRecord(
                extraction_id=extraction_id,
                input_id=input_id,
                extracted_json={"task_name": "Phase 4 workflow"},
                missing_fields=[],
                low_confidence_fields=[],
                confirm_questions=[],
            )
        )
    return References(
        department_id,
        creator,
        assignee,
        reviewer,
        outsider,
        input_id,
        extraction_id,
    )


def _command(
    refs: References,
    records: Phase4Records,
    *,
    self_assigned: bool = False,
) -> tuple[CreateTaskDraftCommand, UUID, UUID]:
    task_id = uuid4()
    first_node_id = uuid4()
    second_node_id = uuid4()
    records.task_ids.add(task_id)
    assignee = refs.creator if self_assigned else refs.assignee
    return (
        CreateTaskDraftCommand(
            task_id=task_id,
            task_name="Phase 4 Core Workflow",
            creator_employee_no=refs.creator,
            main_assignee_employee_no=assignee,
            reviewer_employee_no=refs.reviewer,
            department_id=refs.department_id,
            operation_source="phase4-integration",
            acceptance_criteria="Both nodes completed",
            nodes=(
                TaskNodeDraft(
                    first_node_id,
                    1,
                    "Prepare",
                    owner_employee_no=assignee,
                ),
                TaskNodeDraft(
                    second_node_id,
                    2,
                    "Deliver",
                    owner_employee_no=assignee,
                ),
            ),
            dependencies=(
                TaskNodeDependencyDraft(first_node_id, second_node_id),
            ),
            node_participants=(
                TaskNodeParticipantDraft(first_node_id, assignee, "owner"),
            ),
            extraction_record_ids=(refs.extraction_id,),
        ),
        first_node_id,
        second_node_id,
    )


def _services(factory: sessionmaker[Session]):
    clock = StepClock()

    def uow_factory() -> UnitOfWork:
        return UnitOfWork(factory)

    return (
        TaskWorkflowService(uow_factory, clock=clock),
        TaskNodeWorkflowService(uow_factory, clock=clock),
    )


def test_complete_core_workflow_reaches_completed_with_continuous_logs(
    phase4_session_factory: sessionmaker[Session],
    phase4_records: Phase4Records,
) -> None:
    refs = _create_references(phase4_session_factory, phase4_records)
    command, first_node_id, second_node_id = _command(refs, phase4_records)
    tasks, nodes = _services(phase4_session_factory)

    task = tasks.create_task_draft(command)
    tasks.submit_for_confirmation(task.task_id, refs.creator, 1, "phase4-integration")
    tasks.confirm_and_send(task.task_id, refs.creator, 2, "phase4-integration")
    tasks.accept_task(task.task_id, refs.assignee, 3, "phase4-integration")

    with pytest.raises(DependencyNotSatisfiedError):
        nodes.start_node(
            task.task_id,
            second_node_id,
            refs.assignee,
            4,
            "phase4-integration",
        )

    nodes.start_node(
        task.task_id,
        first_node_id,
        refs.assignee,
        4,
        "phase4-integration",
    )
    nodes.update_node_progress(
        task.task_id,
        first_node_id,
        refs.assignee,
        5,
        "phase4-integration",
        60,
        Decimal("1.5"),
    )
    nodes.complete_node(
        task.task_id,
        first_node_id,
        refs.assignee,
        6,
        "phase4-integration",
    )
    nodes.start_node(
        task.task_id,
        second_node_id,
        refs.assignee,
        7,
        "phase4-integration",
    )
    nodes.complete_node(
        task.task_id,
        second_node_id,
        refs.assignee,
        8,
        "phase4-integration",
    )
    _, review = tasks.submit_completion(
        task.task_id,
        refs.assignee,
        9,
        "phase4-integration",
        "All planned work is complete",
        "Both workflow deliverables are ready",
    )
    tasks.approve_completion(
        task.task_id,
        refs.reviewer,
        10,
        "phase4-integration",
        review.completion_review_id,
    )

    with phase4_session_factory() as session:
        stored_task = TaskRepository(session).get_by_id(task.task_id)
        assert stored_task is not None
        assert stored_task.status == "completed"
        assert stored_task.completed_at is not None
        assert stored_task.task_version == 11
        stored_nodes = TaskNodeRepository(session).list_nodes(task.task_id)
        assert [(node.status, node.progress_percent) for node in stored_nodes] == [
            ("completed", 100),
            ("completed", 100),
        ]
        logs = TaskStatusLogRepository(session).list_by_task_id(task.task_id)
        assert [log.task_version for log in logs] == list(range(1, 12))
        assert [log.action_type for log in logs] == [
            "task_created",
            "submitted_for_confirmation",
            "confirmed_and_sent",
            "task_accepted",
            "node_started",
            "node_progress_updated",
            "node_completed",
            "node_started",
            "node_completed",
            "completion_submitted",
            "completion_approved",
        ]
        assert [
            (log.business_ref_type, log.business_ref_id)
            for log in logs[-2:]
        ] == [
            ("completion_review", review.completion_review_id),
            ("completion_review", review.completion_review_id),
        ]
        stored_review = session.get(
            TaskCompletionReview,
            review.completion_review_id,
        )
        assert stored_review is not None
        assert (
            stored_review.review_round,
            stored_review.review_status,
            stored_review.review_result,
            stored_review.submitted_task_version,
            stored_review.reviewed_task_version,
        ) == (1, "approved", "approved", 10, 11)
        extraction = session.get(AIExtractionRecord, refs.extraction_id)
        assert extraction is not None and extraction.task_id == task.task_id
        participant = TaskRepository(session).find_participant(
            task.task_id,
            refs.assignee,
            "assignee",
        )
        assert participant is not None
        assert participant.is_primary is True
        assert participant.confirm_status == "accepted"

    with pytest.raises(InvalidStateTransitionError):
        nodes.start_node(
            task.task_id,
            first_node_id,
            refs.assignee,
            11,
            "phase4-integration",
        )


def test_return_resend_and_accept_flow(
    phase4_session_factory: sessionmaker[Session],
    phase4_records: Phase4Records,
) -> None:
    refs = _create_references(phase4_session_factory, phase4_records)
    command, _, _ = _command(refs, phase4_records)
    tasks, _ = _services(phase4_session_factory)
    task = tasks.create_task_draft(command)
    tasks.submit_for_confirmation(task.task_id, refs.creator, 1, "phase4-integration")
    tasks.confirm_and_send(task.task_id, refs.creator, 2, "phase4-integration")

    with pytest.raises(BusinessValidationError):
        tasks.return_task(
            task.task_id,
            refs.assignee,
            3,
            "phase4-integration",
            "  ",
        )
    tasks.return_task(
        task.task_id,
        refs.assignee,
        3,
        "phase4-integration",
        "Need clarification",
    )
    tasks.resend_task(task.task_id, refs.creator, 4, "phase4-integration")
    tasks.accept_task(task.task_id, refs.assignee, 5, "phase4-integration")

    with phase4_session_factory() as session:
        stored = session.get(Task, task.task_id)
        assert stored is not None
        assert (stored.status, stored.task_version) == ("in_progress", 6)
        logs = TaskStatusLogRepository(session).list_by_task_id(task.task_id)
        assert [log.action_type for log in logs][-3:] == [
            "task_returned",
            "task_resent",
            "task_accepted",
        ]
        assert logs[-3].reason == "Need clarification"


def test_self_assigned_confirmation_flow(
    phase4_session_factory: sessionmaker[Session],
    phase4_records: Phase4Records,
) -> None:
    refs = _create_references(phase4_session_factory, phase4_records)
    command, _, _ = _command(refs, phase4_records, self_assigned=True)
    tasks, _ = _services(phase4_session_factory)
    task = tasks.create_task_draft(command)
    tasks.submit_for_confirmation(task.task_id, refs.creator, 1, "phase4-integration")
    tasks.confirm_self_assigned(task.task_id, refs.creator, 2, "phase4-integration")

    with phase4_session_factory() as session:
        stored = session.get(Task, task.task_id)
        assert stored is not None
        assert (stored.status, stored.task_version) == ("in_progress", 3)
        assert stored.confirmed_at == stored.sent_at == stored.accepted_at
        participant = TaskRepository(session).find_participant(
            task.task_id,
            refs.creator,
            "assignee",
        )
        assert participant is not None
        assert participant.confirm_status == "accepted"


def test_version_conflict_and_permission_failure_leave_no_partial_changes(
    phase4_session_factory: sessionmaker[Session],
    phase4_records: Phase4Records,
) -> None:
    refs = _create_references(phase4_session_factory, phase4_records)
    command, _, _ = _command(refs, phase4_records)
    tasks, _ = _services(phase4_session_factory)
    task = tasks.create_task_draft(command)

    with pytest.raises(TaskVersionConflictError):
        tasks.submit_for_confirmation(task.task_id, refs.creator, 0, "phase4-integration")
    with pytest.raises(PermissionDeniedError):
        tasks.submit_for_confirmation(
            task.task_id,
            refs.outsider,
            1,
            "phase4-integration",
        )

    with phase4_session_factory() as session:
        stored = session.get(Task, task.task_id)
        assert stored is not None
        assert (stored.status, stored.task_version) == ("draft", 1)
        logs = TaskStatusLogRepository(session).list_by_task_id(task.task_id)
        assert [log.action_type for log in logs] == ["task_created"]


def test_cycle_is_rejected_without_persisting_task(
    phase4_session_factory: sessionmaker[Session],
    phase4_records: Phase4Records,
) -> None:
    refs = _create_references(phase4_session_factory, phase4_records)
    command, first, second = _command(refs, phase4_records)
    cyclic = replace(
        command,
        dependencies=(
            TaskNodeDependencyDraft(first, second),
            TaskNodeDependencyDraft(second, first),
        ),
    )
    tasks, _ = _services(phase4_session_factory)

    with pytest.raises(DependencyCycleError):
        tasks.create_task_draft(cyclic)

    with phase4_session_factory() as session:
        assert session.get(Task, command.task_id) is None
        extraction = session.get(AIExtractionRecord, refs.extraction_id)
        assert extraction is not None and extraction.task_id is None


def test_mid_transaction_exception_rolls_back_entire_draft(
    phase4_session_factory: sessionmaker[Session],
    phase4_records: Phase4Records,
) -> None:
    refs = _create_references(phase4_session_factory, phase4_records)
    command, _, _ = _command(refs, phase4_records)

    class FailingLogUnitOfWork(UnitOfWork):
        def __enter__(self):
            entered = super().__enter__()

            def fail_after_aggregate(_log: TaskStatusLog) -> TaskStatusLog:
                raise RuntimeError("forced status log failure")

            self.task_status_logs.add = fail_after_aggregate
            return entered

    service = TaskWorkflowService(
        lambda: FailingLogUnitOfWork(phase4_session_factory),
        clock=StepClock(),
    )

    with pytest.raises(RuntimeError, match="forced status log failure"):
        service.create_task_draft(command)

    with phase4_session_factory() as session:
        assert session.get(Task, command.task_id) is None
        assert session.scalar(
            select(TaskNode).where(TaskNode.task_id == command.task_id).limit(1)
        ) is None
        extraction = session.get(AIExtractionRecord, refs.extraction_id)
        assert extraction is not None and extraction.task_id is None


def test_database_constraint_error_rolls_back_second_draft(
    phase4_session_factory: sessionmaker[Session],
    phase4_records: Phase4Records,
) -> None:
    refs = _create_references(phase4_session_factory, phase4_records)
    first_command, _, _ = _command(refs, phase4_records)
    tasks, _ = _services(phase4_session_factory)
    tasks.create_task_draft(first_command)

    second_input_id = uuid4()
    second_extraction_id = uuid4()
    phase4_records.input_ids.add(second_input_id)
    phase4_records.extraction_ids.add(second_extraction_id)
    with phase4_session_factory.begin() as session:
        session.add(
            TaskInput(
                input_id=second_input_id,
                input_type="text",
                source_channel="phase4-integration",
                submitted_by_employee_no=refs.creator,
            )
        )
        session.add(
            AIExtractionRecord(
                extraction_id=second_extraction_id,
                input_id=second_input_id,
                extracted_json={},
                missing_fields=[],
                low_confidence_fields=[],
                confirm_questions=[],
            )
        )
    duplicate = replace(
        first_command,
        extraction_record_ids=(second_extraction_id,),
    )

    with pytest.raises(IntegrityError):
        tasks.create_task_draft(duplicate)

    with phase4_session_factory() as session:
        extraction = session.get(AIExtractionRecord, second_extraction_id)
        assert extraction is not None and extraction.task_id is None
        logs = TaskStatusLogRepository(session).list_by_task_id(first_command.task_id)
        assert [log.action_type for log in logs] == ["task_created"]
