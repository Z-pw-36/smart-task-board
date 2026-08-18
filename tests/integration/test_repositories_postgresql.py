from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, create_engine, delete, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.db.unit_of_work import UnitOfWork
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
from app.repositories import (
    AIExtractionRecordRepository,
    TaskInputRepository,
    TaskNodeRepository,
    TaskRepository,
    TaskStatusLogRepository,
    UserRepository,
)

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
class CreatedRecords:
    department_ids: set[UUID] = field(default_factory=set)
    employee_nos: set[str] = field(default_factory=set)
    input_ids: set[UUID] = field(default_factory=set)
    extraction_ids: set[UUID] = field(default_factory=set)
    task_ids: set[UUID] = field(default_factory=set)
    participant_ids: set[UUID] = field(default_factory=set)
    node_ids: set[UUID] = field(default_factory=set)
    dependency_ids: set[UUID] = field(default_factory=set)
    node_participant_ids: set[UUID] = field(default_factory=set)
    status_log_ids: set[UUID] = field(default_factory=set)


@dataclass(frozen=True)
class SeededGraph:
    department_id: UUID
    employee_no: str
    second_employee_no: str
    input_id: UUID
    extraction_id: UUID
    task_id: UUID
    participant_id: UUID
    first_node_id: UUID
    second_node_id: UUID
    dependency_id: UUID
    node_participant_id: UUID
    status_log_id: UUID


@pytest.fixture(scope="session")
def postgresql_engine() -> Iterator[Engine]:
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
        pytest.fail("PostgreSQL integration target is not the approved isolated database")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "options": "-c statement_timeout=5000 -c lock_timeout=1000"
        },
    )
    try:
        database_tables = set(inspect(engine).get_table_names(schema="public"))
        assert database_tables - {"alembic_version"} == EXPECTED_TABLES
        with engine.connect() as connection:
            revisions = connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalars().all()
        assert revisions == [EXPECTED_REVISION]
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session_factory(
    postgresql_engine: Engine,
) -> sessionmaker[Session]:
    return sessionmaker(
        bind=postgresql_engine,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture
def created_records(
    postgresql_engine: Engine,
) -> Iterator[CreatedRecords]:
    records = CreatedRecords()
    yield records
    with postgresql_engine.begin() as connection:
        cleanup_steps = (
            (TaskStatusLog, TaskStatusLog.status_log_id, records.status_log_ids),
            (
                TaskNodeDependency,
                TaskNodeDependency.dependency_id,
                records.dependency_ids,
            ),
            (
                TaskNodeParticipant,
                TaskNodeParticipant.node_participant_id,
                records.node_participant_ids,
            ),
            (TaskParticipant, TaskParticipant.participant_id, records.participant_ids),
            (
                AIExtractionRecord,
                AIExtractionRecord.extraction_id,
                records.extraction_ids,
            ),
            (TaskNode, TaskNode.node_id, records.node_ids),
            (Task, Task.task_id, records.task_ids),
            (TaskInput, TaskInput.input_id, records.input_ids),
            (User, User.employee_no, records.employee_nos),
            (Department, Department.department_id, records.department_ids),
        )
        for model, column, identifiers in cleanup_steps:
            if identifiers:
                connection.execute(delete(model).where(column.in_(identifiers)))


def _new_employee_no(label: str) -> str:
    return f"P3-{label}-{uuid4().hex[:12]}"


def _seed_graph(
    factory: sessionmaker[Session],
    records: CreatedRecords,
) -> SeededGraph:
    department_id = uuid4()
    employee_no = _new_employee_no("owner")
    second_employee_no = _new_employee_no("collaborator")
    task_id = uuid4()
    participant_id = uuid4()
    first_node_id = uuid4()
    second_node_id = uuid4()
    dependency_id = uuid4()
    node_participant_id = uuid4()
    status_log_id = uuid4()

    records.department_ids.add(department_id)
    records.employee_nos.update({employee_no, second_employee_no})
    records.task_ids.add(task_id)
    records.participant_ids.add(participant_id)
    records.node_ids.update({first_node_id, second_node_id})
    records.dependency_ids.add(dependency_id)
    records.node_participant_ids.add(node_participant_id)
    records.status_log_ids.add(status_log_id)

    with UnitOfWork(factory) as uow:
        assert uow.session is not None
        department = Department(
            department_id=department_id,
            department_name="Phase 3 Integration",
            department_type="team",
            department_path=f"/{department_id}",
            status="active",
        )
        owner = User(
            employee_no=employee_no,
            name="Phase 3 Owner",
            department_id=department_id,
            role_type="employee",
            status="active",
        )
        collaborator = User(
            employee_no=second_employee_no,
            name="Phase 3 Collaborator",
            department_id=department_id,
            role_type="employee",
            status="active",
        )
        uow.session.add(department)
        uow.session.flush()
        uow.session.add_all([owner, collaborator])
        uow.session.flush()

        task_input = TaskInput(
            input_type="text",
            raw_text="Phase 3 repository integration test",
            source_channel="integration-test",
            submitted_by_employee_no=employee_no,
        )
        assert task_input.input_id is None
        uow.task_inputs.add(task_input)
        assert task_input.input_id is not None
        records.input_ids.add(task_input.input_id)

        task = Task(
            task_id=task_id,
            task_no=f"P3-{task_id.hex}",
            task_name="Phase 3 Integration Task",
            creator_employee_no=employee_no,
            main_assignee_employee_no=employee_no,
            department_id=department_id,
            status="draft",
            task_version=1,
        )
        uow.tasks.add(task)

        extraction = AIExtractionRecord(
            input_id=task_input.input_id,
            task_id=task_id,
            extracted_json={"task_name": task.task_name},
            missing_fields=[],
            low_confidence_fields=[],
            confirm_questions=[],
        )
        uow.ai_extraction_records.add(extraction)
        records.extraction_ids.add(extraction.extraction_id)

        participant = TaskParticipant(
            participant_id=participant_id,
            task_id=task_id,
            employee_no=employee_no,
            participant_role="assignee",
            is_primary=True,
        )
        uow.tasks.add_participant(participant)

        first_node = TaskNode(
            node_id=first_node_id,
            task_id=task_id,
            node_order=1,
            sort_weight=0,
            node_name="First node",
            owner_employee_no=employee_no,
        )
        second_node = TaskNode(
            node_id=second_node_id,
            task_id=task_id,
            node_order=2,
            sort_weight=0,
            node_name="Second node",
            owner_employee_no=employee_no,
        )
        uow.task_nodes.add_node(first_node)
        uow.task_nodes.add_node(second_node)

        node_participant = TaskNodeParticipant(
            node_participant_id=node_participant_id,
            task_id=task_id,
            node_id=first_node_id,
            employee_no=employee_no,
            participant_role="owner",
        )
        uow.task_nodes.add_participant(node_participant)

        dependency = TaskNodeDependency(
            dependency_id=dependency_id,
            task_id=task_id,
            predecessor_node_id=first_node_id,
            successor_node_id=second_node_id,
            dependency_type="finish_to_start",
        )
        uow.task_nodes.add_dependency(dependency)

        status_log = TaskStatusLog(
            status_log_id=status_log_id,
            task_id=task_id,
            from_status=None,
            to_status="draft",
            action_type="create",
            operator_employee_no=employee_no,
            task_version=1,
            operation_source="integration-test",
        )
        uow.task_status_logs.add(status_log)
        uow.commit()

    return SeededGraph(
        department_id=department_id,
        employee_no=employee_no,
        second_employee_no=second_employee_no,
        input_id=task_input.input_id,
        extraction_id=extraction.extraction_id,
        task_id=task_id,
        participant_id=participant_id,
        first_node_id=first_node_id,
        second_node_id=second_node_id,
        dependency_id=dependency_id,
        node_participant_id=node_participant_id,
        status_log_id=status_log_id,
    )


def test_successful_commit_is_visible_to_a_new_session(
    session_factory: sessionmaker[Session],
    created_records: CreatedRecords,
) -> None:
    graph = _seed_graph(session_factory, created_records)

    with session_factory() as session:
        assert UserRepository(session).get_by_employee_no(graph.employee_no) is not None
        assert TaskInputRepository(session).get_by_id(graph.input_id) is not None
        assert (
            AIExtractionRecordRepository(session).get_by_id(graph.extraction_id)
            is not None
        )
        tasks = TaskRepository(session)
        assert tasks.get_by_id(graph.task_id) is not None
        assert tasks.get_participant(graph.participant_id) is not None
        nodes = TaskNodeRepository(session)
        assert [node.node_id for node in nodes.list_nodes(graph.task_id)] == [
            graph.first_node_id,
            graph.second_node_id,
        ]
        assert nodes.get_dependency(graph.dependency_id) is not None
        assert nodes.get_participant(graph.node_participant_id) is not None
        assert (
            TaskStatusLogRepository(session).get_by_id(graph.status_log_id)
            is not None
        )


def test_exception_rolls_back_all_objects_atomically(
    session_factory: sessionmaker[Session],
    created_records: CreatedRecords,
) -> None:
    department_id = uuid4()
    employee_no = _new_employee_no("rollback")
    created_records.department_ids.add(department_id)
    created_records.employee_nos.add(employee_no)

    with pytest.raises(RuntimeError, match="force atomic rollback"):
        with UnitOfWork(session_factory) as uow:
            assert uow.session is not None
            uow.session.add(
                Department(
                    department_id=department_id,
                    department_name="Rollback Department",
                    department_type="team",
                    department_path=f"/{department_id}",
                    status="active",
                )
            )
            uow.session.flush()
            uow.session.add(
                User(
                    employee_no=employee_no,
                    name="Rollback User",
                    department_id=department_id,
                    role_type="employee",
                    status="active",
                )
            )
            uow.session.flush()
            raise RuntimeError("force atomic rollback")

    with session_factory() as session:
        assert UserRepository(session).get_by_employee_no(employee_no) is None
        assert session.get(Department, department_id) is None


def test_duplicate_task_participant_unique_constraint_is_enforced(
    session_factory: sessionmaker[Session],
    created_records: CreatedRecords,
) -> None:
    graph = _seed_graph(session_factory, created_records)
    invalid_id = uuid4()
    created_records.participant_ids.add(invalid_id)

    with pytest.raises(IntegrityError):
        with UnitOfWork(session_factory) as uow:
            uow.tasks.add_participant(
                TaskParticipant(
                    participant_id=invalid_id,
                    task_id=graph.task_id,
                    employee_no=graph.employee_no,
                    participant_role="assignee",
                    is_primary=False,
                )
            )


def test_one_primary_assignee_partial_unique_index_is_enforced(
    session_factory: sessionmaker[Session],
    created_records: CreatedRecords,
) -> None:
    graph = _seed_graph(session_factory, created_records)
    invalid_id = uuid4()
    created_records.participant_ids.add(invalid_id)

    with pytest.raises(IntegrityError):
        with UnitOfWork(session_factory) as uow:
            uow.tasks.add_participant(
                TaskParticipant(
                    participant_id=invalid_id,
                    task_id=graph.task_id,
                    employee_no=graph.second_employee_no,
                    participant_role="assignee",
                    is_primary=True,
                )
            )


def test_task_node_dependency_self_reference_check_is_enforced(
    session_factory: sessionmaker[Session],
    created_records: CreatedRecords,
) -> None:
    graph = _seed_graph(session_factory, created_records)
    invalid_id = uuid4()
    created_records.dependency_ids.add(invalid_id)

    with pytest.raises(IntegrityError):
        with UnitOfWork(session_factory) as uow:
            uow.task_nodes.add_dependency(
                TaskNodeDependency(
                    dependency_id=invalid_id,
                    task_id=graph.task_id,
                    predecessor_node_id=graph.first_node_id,
                    successor_node_id=graph.first_node_id,
                    dependency_type="finish_to_start",
                )
            )


def test_cross_task_node_composite_foreign_key_is_enforced(
    session_factory: sessionmaker[Session],
    created_records: CreatedRecords,
) -> None:
    graph = _seed_graph(session_factory, created_records)
    second_task_id = uuid4()
    foreign_node_id = uuid4()
    invalid_dependency_id = uuid4()
    created_records.task_ids.add(second_task_id)
    created_records.node_ids.add(foreign_node_id)
    created_records.dependency_ids.add(invalid_dependency_id)

    with pytest.raises(IntegrityError):
        with UnitOfWork(session_factory) as uow:
            uow.tasks.add(
                Task(
                    task_id=second_task_id,
                    task_no=f"P3-{second_task_id.hex}",
                    task_name="Foreign task",
                    creator_employee_no=graph.employee_no,
                    status="draft",
                    task_version=1,
                )
            )
            uow.task_nodes.add_node(
                TaskNode(
                    node_id=foreign_node_id,
                    task_id=second_task_id,
                    node_order=1,
                    node_name="Foreign node",
                )
            )
            uow.task_nodes.add_dependency(
                TaskNodeDependency(
                    dependency_id=invalid_dependency_id,
                    task_id=graph.task_id,
                    predecessor_node_id=graph.first_node_id,
                    successor_node_id=foreign_node_id,
                )
            )


def test_status_log_business_reference_pair_check_is_enforced(
    session_factory: sessionmaker[Session],
    created_records: CreatedRecords,
) -> None:
    graph = _seed_graph(session_factory, created_records)
    invalid_id = uuid4()
    created_records.status_log_ids.add(invalid_id)

    with pytest.raises(IntegrityError):
        with UnitOfWork(session_factory) as uow:
            uow.task_status_logs.add(
                TaskStatusLog(
                    status_log_id=invalid_id,
                    task_id=graph.task_id,
                    to_status="draft",
                    action_type="invalid-reference",
                    operator_employee_no=graph.employee_no,
                    task_version=1,
                    business_ref_type="node",
                    business_ref_id=None,
                    operation_source="integration-test",
                )
            )


def test_task_for_update_blocks_a_second_session_with_bounded_timeout(
    session_factory: sessionmaker[Session],
    created_records: CreatedRecords,
) -> None:
    graph = _seed_graph(session_factory, created_records)
    first_session = session_factory()
    second_session = session_factory()
    try:
        locked_task = TaskRepository(first_session).get_by_id_for_update(graph.task_id)
        assert locked_task is not None
        second_session.execute(text("SET LOCAL lock_timeout = '500ms'"))
        with pytest.raises(OperationalError):
            TaskRepository(second_session).get_by_id_for_update(graph.task_id)
        second_session.rollback()
    finally:
        first_session.rollback()
        second_session.rollback()
        first_session.close()
        second_session.close()
