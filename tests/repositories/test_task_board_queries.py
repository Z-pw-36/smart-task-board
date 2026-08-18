from datetime import UTC, datetime
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from app.repositories.task import TaskRepository


def _sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"render_postcompile": True},
        )
    )


def test_related_predicate_uses_only_task_relationships_not_global_roles() -> None:
    sql = _sql(TaskRepository._filtered_related_statement("E-ACTOR"))
    assert "creator_employee_no" in sql
    assert "main_assignee_employee_no" in sql
    assert "task_participants" in sql
    assert "task_nodes" in sql
    assert "task_node_participants" in sql
    assert "report_to_employee_no" in sql
    assert "reviewer_employee_no" in sql
    assert "role_type" not in sql


def test_task_list_is_parameterized_bounded_and_stably_sorted() -> None:
    session = MagicMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []
    session.execute.side_effect = [count_result, list_result]
    repository = TaskRepository(session)
    tasks, total = repository.list_related(
        "E-ACTOR",
        relation="participating",
        task_status="in_progress",
        search="100%_safe' OR true",
        deadline_from=datetime(2026, 8, 1, tzinfo=UTC),
        deadline_to=datetime(2026, 9, 1, tzinfo=UTC),
        limit=20,
        offset=5,
    )
    assert tasks == []
    assert total == 0
    list_statement = session.execute.call_args_list[1].args[0]
    sql = _sql(list_statement)
    assert "100%_safe" not in sql
    assert "ORDER BY coalesce(tasks.is_urgent" in sql
    assert "tasks.deadline ASC NULLS LAST" in sql
    assert "tasks.created_at DESC" in sql
    assert "LIMIT" in sql and "OFFSET" in sql


def test_inbox_candidates_exclude_node_participant_and_admin_shortcuts() -> None:
    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    repository = TaskRepository(session)
    assert repository.list_inbox_candidates("E-ACTOR") == []
    statement = session.execute.call_args.args[0]
    sql = _sql(statement)
    assert "task_node_participants" not in sql
    assert "role_type" not in sql
    assert "owner_employee_no" in sql
    assert "LIMIT" in sql
