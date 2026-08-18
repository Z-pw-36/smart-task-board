from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models import (
    AIExtractionRecord,
    Task,
    TaskInput,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskStatusLog,
)
from app.repositories import (
    AIExtractionRecordRepository,
    DepartmentRepository,
    TaskInputRepository,
    TaskNodeRepository,
    TaskRepository,
    TaskStatusLogRepository,
    UserRepository,
)


def _session_with_result(
    *,
    scalar: object | None = None,
    rows: list[object] | None = None,
) -> MagicMock:
    session = MagicMock(spec=Session)
    result = session.execute.return_value
    result.scalar_one_or_none.return_value = scalar
    result.scalars.return_value.all.return_value = rows or []
    return session


def _executed_sql(session: MagicMock) -> str:
    statement = session.execute.call_args.args[0]
    compiled = statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    return " ".join(str(compiled).split())


def test_reference_repositories_filter_lock_and_sort_stably() -> None:
    department_id = uuid4()
    session = _session_with_result()
    departments = DepartmentRepository(session)
    users = UserRepository(session)

    assert departments.get_by_id(department_id) is None
    assert f"departments.department_id = '{department_id}'" in _executed_sql(session)

    assert departments.get_by_name("Engineering") is None
    department_sql = _executed_sql(session)
    assert "departments.department_name = 'Engineering'" in department_sql
    assert (
        "ORDER BY departments.department_path, departments.department_id"
        in department_sql
    )
    assert "LIMIT 1" in department_sql

    assert users.get_by_employee_no("E001") is None
    assert "users.employee_no = 'E001'" in _executed_sql(session)

    assert users.get_by_employee_no_for_update("E001") is None
    assert _executed_sql(session).endswith("FOR UPDATE")

    assert users.list_by_department(department_id) == []
    user_sql = _executed_sql(session)
    assert f"users.department_id = '{department_id}'" in user_sql
    assert "ORDER BY users.name, users.employee_no" in user_sql


def test_add_repositories_flush_but_never_control_transactions() -> None:
    session = _session_with_result()
    task_input = TaskInput(
        input_type="text",
        source_channel="unit-test",
        submitted_by_employee_no="E001",
    )
    extraction = AIExtractionRecord(
        input_id=uuid4(),
        extracted_json={},
        missing_fields=[],
        low_confidence_fields=[],
        confirm_questions=[],
    )
    task = Task(task_name="Task", creator_employee_no="E001", status="draft")
    task_participant = TaskParticipant(
        task_id=uuid4(),
        employee_no="E001",
        participant_role="assignee",
    )
    node = TaskNode(task_id=uuid4(), node_order=1, node_name="Node")
    dependency = TaskNodeDependency(
        task_id=uuid4(),
        predecessor_node_id=uuid4(),
        successor_node_id=uuid4(),
    )
    node_participant = TaskNodeParticipant(
        task_id=uuid4(),
        node_id=uuid4(),
        employee_no="E001",
        participant_role="owner",
    )
    status_log = TaskStatusLog(
        task_id=uuid4(),
        to_status="draft",
        action_type="create",
        task_version=1,
        operation_source="unit-test",
    )

    assert TaskInputRepository(session).add(task_input) is task_input
    assert AIExtractionRecordRepository(session).add(extraction) is extraction
    task_repository = TaskRepository(session)
    assert task_repository.add(task) is task
    assert task_repository.add_participant(task_participant) is task_participant
    node_repository = TaskNodeRepository(session)
    assert node_repository.add_node(node) is node
    assert node_repository.add_dependency(dependency) is dependency
    assert node_repository.add_participant(node_participant) is node_participant
    assert TaskStatusLogRepository(session).add(status_log) is status_log

    assert session.add.call_count == 8
    assert session.flush.call_count == 8
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_task_input_and_extraction_queries_use_explicit_ids_and_stable_order() -> None:
    input_id = uuid4()
    task_id = uuid4()
    extraction_id = uuid4()
    session = _session_with_result()

    assert TaskInputRepository(session).get_by_id(input_id) is None
    assert f"task_inputs.input_id = '{input_id}'" in _executed_sql(session)

    repository = AIExtractionRecordRepository(session)
    assert repository.get_by_id(extraction_id) is None
    assert (
        f"ai_extraction_records.extraction_id = '{extraction_id}'"
        in _executed_sql(session)
    )

    assert repository.list_by_input_id(input_id) == []
    input_sql = _executed_sql(session)
    assert f"ai_extraction_records.input_id = '{input_id}'" in input_sql
    assert "ORDER BY ai_extraction_records.extraction_id" in input_sql

    assert repository.list_by_task_id(task_id) == []
    task_sql = _executed_sql(session)
    assert f"ai_extraction_records.task_id = '{task_id}'" in task_sql
    assert "ORDER BY ai_extraction_records.extraction_id" in task_sql


def test_task_repository_filters_locks_and_uses_stable_ordering() -> None:
    task_id = uuid4()
    participant_id = uuid4()
    session = _session_with_result()
    repository = TaskRepository(session)

    assert repository.get_by_id(task_id) is None
    assert f"tasks.task_id = '{task_id}'" in _executed_sql(session)

    assert repository.get_by_id_for_update(task_id) is None
    assert _executed_sql(session).endswith("FOR UPDATE")

    assert repository.get_by_task_no("TASK-001") is None
    assert "tasks.task_no = 'TASK-001'" in _executed_sql(session)

    assert repository.list_created_by("E001") == []
    created_sql = _executed_sql(session)
    assert "tasks.creator_employee_no = 'E001'" in created_sql
    assert "ORDER BY tasks.created_at DESC, tasks.task_id" in created_sql

    assert repository.list_assigned_to("E002") == []
    assigned_sql = _executed_sql(session)
    assert "tasks.main_assignee_employee_no = 'E002'" in assigned_sql
    assert "ORDER BY tasks.created_at DESC, tasks.task_id" in assigned_sql

    assert repository.get_participant(participant_id) is None
    assert (
        f"task_participants.participant_id = '{participant_id}'"
        in _executed_sql(session)
    )

    assert repository.list_participants(task_id) == []
    participants_sql = _executed_sql(session)
    assert f"task_participants.task_id = '{task_id}'" in participants_sql
    assert (
        "ORDER BY task_participants.participant_role, "
        "task_participants.employee_no, task_participants.participant_id"
        in participants_sql
    )

    assert repository.find_participant(task_id, "E001", "assignee") is None
    find_sql = _executed_sql(session)
    assert f"task_participants.task_id = '{task_id}'" in find_sql
    assert "task_participants.employee_no = 'E001'" in find_sql
    assert "task_participants.participant_role = 'assignee'" in find_sql


def test_task_node_repository_filters_locks_and_orders_all_collections() -> None:
    task_id = uuid4()
    node_id = uuid4()
    other_node_id = uuid4()
    dependency_id = uuid4()
    participant_id = uuid4()
    session = _session_with_result()
    repository = TaskNodeRepository(session)

    assert repository.get_node(node_id) is None
    assert f"task_nodes.node_id = '{node_id}'" in _executed_sql(session)

    assert repository.get_node_for_update(node_id) is None
    assert _executed_sql(session).endswith("FOR UPDATE")

    assert repository.list_nodes(task_id) == []
    node_sql = _executed_sql(session)
    assert f"task_nodes.task_id = '{task_id}'" in node_sql
    assert (
        "ORDER BY task_nodes.node_order, task_nodes.sort_weight, "
        "task_nodes.node_id" in node_sql
    )

    assert repository.get_dependency(dependency_id) is None
    assert (
        f"task_node_dependencies.dependency_id = '{dependency_id}'"
        in _executed_sql(session)
    )

    assert repository.list_dependencies(task_id) == []
    dependency_sql = _executed_sql(session)
    assert f"task_node_dependencies.task_id = '{task_id}'" in dependency_sql
    assert "ORDER BY task_node_dependencies.predecessor_node_id" in dependency_sql
    assert "task_node_dependencies.dependency_id" in dependency_sql

    assert repository.list_predecessors(task_id, node_id) == []
    predecessor_sql = _executed_sql(session)
    assert f"task_node_dependencies.task_id = '{task_id}'" in predecessor_sql
    assert f"task_node_dependencies.successor_node_id = '{node_id}'" in predecessor_sql
    assert "ORDER BY task_node_dependencies.predecessor_node_id" in predecessor_sql

    assert repository.list_successors(task_id, other_node_id) == []
    successor_sql = _executed_sql(session)
    assert f"task_node_dependencies.task_id = '{task_id}'" in successor_sql
    assert (
        f"task_node_dependencies.predecessor_node_id = '{other_node_id}'"
        in successor_sql
    )
    assert "ORDER BY task_node_dependencies.successor_node_id" in successor_sql

    assert repository.get_participant(participant_id) is None
    assert (
        f"task_node_participants.node_participant_id = '{participant_id}'"
        in _executed_sql(session)
    )

    assert repository.list_participants(task_id, node_id) == []
    participant_sql = _executed_sql(session)
    assert f"task_node_participants.task_id = '{task_id}'" in participant_sql
    assert f"task_node_participants.node_id = '{node_id}'" in participant_sql
    assert (
        "ORDER BY task_node_participants.participant_role, "
        "task_node_participants.employee_no, "
        "task_node_participants.node_participant_id" in participant_sql
    )

    assert repository.list_participants_by_task_id(task_id) == []
    task_participant_sql = _executed_sql(session)
    assert f"task_node_participants.task_id = '{task_id}'" in task_participant_sql
    assert "ORDER BY task_node_participants.node_id" in task_participant_sql

    assert repository.find_participant(task_id, node_id, "E001", "owner") is None
    find_sql = _executed_sql(session)
    assert "task_node_participants.employee_no = 'E001'" in find_sql
    assert "task_node_participants.participant_role = 'owner'" in find_sql


def test_status_log_repository_is_append_only_and_orders_timeline_stably() -> None:
    task_id = uuid4()
    status_log_id = uuid4()
    session = _session_with_result()
    repository = TaskStatusLogRepository(session)

    assert repository.get_by_id(status_log_id) is None
    assert (
        f"task_status_logs.status_log_id = '{status_log_id}'"
        in _executed_sql(session)
    )

    assert repository.list_by_task_id(task_id) == []
    timeline_sql = _executed_sql(session)
    assert f"task_status_logs.task_id = '{task_id}'" in timeline_sql
    assert (
        "ORDER BY task_status_logs.created_at, task_status_logs.status_log_id"
        in timeline_sql
    )

    assert repository.list_by_task_id_paginated(task_id, limit=20, offset=10) == []
    paginated_sql = _executed_sql(session)
    assert "LIMIT 20 OFFSET 10" in paginated_sql

    session.execute.return_value.scalar_one.return_value = 7
    assert repository.count_by_task_id(task_id) == 7
    count_sql = _executed_sql(session)
    assert "count(*)" in count_sql
    assert f"task_status_logs.task_id = '{task_id}'" in count_sql

    assert repository.get_latest_for_task(task_id) is None
    latest_sql = _executed_sql(session)
    assert (
        "ORDER BY task_status_logs.created_at DESC, "
        "task_status_logs.status_log_id DESC" in latest_sql
    )
    assert "LIMIT 1" in latest_sql
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")
