from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models import TaskChangeRequest
from app.repositories import TaskChangeRequestRepository


def _session_with_result() -> MagicMock:
    session = MagicMock(spec=Session)
    result = session.execute.return_value
    result.scalar_one_or_none.return_value = None
    result.scalar_one.return_value = 0
    result.scalars.return_value.all.return_value = []
    return session


def _executed_sql(session: MagicMock) -> str:
    statement = session.execute.call_args.args[0]
    compiled = statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    return " ".join(str(compiled).split())


def test_add_is_append_only_and_does_not_control_transactions() -> None:
    session = _session_with_result()
    repository = TaskChangeRequestRepository(session)
    request = TaskChangeRequest(
        task_id=uuid4(),
        requester_employee_no="E001",
        patch_json={"task_name": "Updated"},
        reason="Clarify the deliverable",
        before_snapshot={"task_name": "Original"},
        after_snapshot={"task_name": "Updated"},
        requester_task_version=3,
        base_task_version=3,
    )

    assert repository.add(request) is request
    session.add.assert_called_once_with(request)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")


def test_identity_and_task_scoped_lock_queries_are_stable() -> None:
    task_id = uuid4()
    request_id = uuid4()
    session = _session_with_result()
    repository = TaskChangeRequestRepository(session)

    assert repository.get_by_id(request_id) is None
    assert f"task_change_requests.change_request_id = '{request_id}'" in _executed_sql(
        session
    )
    assert repository.get_by_id_for_update(request_id) is None
    assert _executed_sql(session).endswith("FOR UPDATE")
    assert repository.get_by_task_and_id_for_update(task_id, request_id) is None
    locked_sql = _executed_sql(session)
    assert f"task_change_requests.task_id = '{task_id}'" in locked_sql
    assert f"task_change_requests.change_request_id = '{request_id}'" in locked_sql
    assert locked_sql.endswith("FOR UPDATE")


def test_pending_and_timeline_queries_filter_status_and_paginate() -> None:
    task_id = uuid4()
    session = _session_with_result()
    repository = TaskChangeRequestRepository(session)

    assert repository.get_pending(task_id) is None
    pending_sql = _executed_sql(session)
    assert f"task_change_requests.task_id = '{task_id}'" in pending_sql
    assert "task_change_requests.status = 'pending'" in pending_sql

    assert repository.get_pending_for_update(task_id) is None
    assert _executed_sql(session).endswith("FOR UPDATE")

    assert repository.list_by_task_id(task_id, status="rejected", limit=20, offset=10) == []
    timeline_sql = _executed_sql(session)
    assert "task_change_requests.status = 'rejected'" in timeline_sql
    assert "ORDER BY task_change_requests.created_at DESC" in timeline_sql
    assert "LIMIT 20 OFFSET 10" in timeline_sql

    session.execute.return_value.scalar_one.return_value = 4
    assert repository.count_by_task_id(task_id, status="approved") == 4
    count_sql = _executed_sql(session)
    assert "count(*)" in count_sql
    assert "task_change_requests.status = 'approved'" in count_sql


def test_pending_and_requester_lists_are_bounded_and_stably_ordered() -> None:
    session = _session_with_result()
    repository = TaskChangeRequestRepository(session)

    assert repository.list_pending(limit=25, offset=5) == []
    pending_sql = _executed_sql(session)
    assert "task_change_requests.status = 'pending'" in pending_sql
    assert "ORDER BY task_change_requests.created_at, " in pending_sql
    assert "LIMIT 25 OFFSET 5" in pending_sql

    assert repository.list_by_requester("E001", limit=30, offset=3) == []
    requester_sql = _executed_sql(session)
    assert "task_change_requests.requester_employee_no = 'E001'" in requester_sql
    assert "LIMIT 30 OFFSET 3" in requester_sql

