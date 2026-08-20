from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.models import TaskCompletionReview
from app.repositories import TaskCompletionReviewRepository


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


def test_add_is_append_oriented_and_does_not_control_transactions() -> None:
    session = _session_with_result()
    repository = TaskCompletionReviewRepository(session)
    review = TaskCompletionReview(
        task_id=uuid4(),
        review_round=1,
        submitted_by_employee_no="E001",
        completion_note="Ready for review",
        deliverable_summary="Release artifact",
        reviewer_employee_no="E002",
        submitted_task_version=3,
    )

    assert repository.add(review) is review

    session.add.assert_called_once_with(review)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    assert not hasattr(repository, "update")
    assert not hasattr(repository, "delete")


def test_identity_current_and_locking_queries_are_task_scoped() -> None:
    task_id = uuid4()
    completion_review_id = uuid4()
    session = _session_with_result()
    repository = TaskCompletionReviewRepository(session)

    assert repository.get_by_id(completion_review_id) is None
    identity_sql = _executed_sql(session)
    assert (
        "task_completion_reviews.completion_review_id = "
        f"'{completion_review_id}'" in identity_sql
    )
    assert "WHERE task_completion_reviews.task_id" not in identity_sql

    assert (
        repository.get_by_task_and_id_for_update(
            task_id,
            completion_review_id,
        )
        is None
    )
    locked_sql = _executed_sql(session)
    assert f"task_completion_reviews.task_id = '{task_id}'" in locked_sql
    assert f"task_completion_reviews.completion_review_id = '{completion_review_id}'" in locked_sql
    assert locked_sql.endswith("FOR UPDATE")

    assert repository.get_current_submitted(task_id) is None
    current_sql = _executed_sql(session)
    assert f"task_completion_reviews.task_id = '{task_id}'" in current_sql
    assert "task_completion_reviews.review_status = 'submitted'" in current_sql
    assert "FOR UPDATE" not in current_sql


def test_latest_queries_use_round_first_stable_ordering() -> None:
    task_id = uuid4()
    session = _session_with_result()
    repository = TaskCompletionReviewRepository(session)

    assert repository.get_latest(task_id) is None
    latest_sql = _executed_sql(session)
    assert f"task_completion_reviews.task_id = '{task_id}'" in latest_sql
    assert (
        "ORDER BY task_completion_reviews.review_round DESC, "
        "task_completion_reviews.submitted_at DESC, "
        "task_completion_reviews.completion_review_id DESC" in latest_sql
    )
    assert "LIMIT 1" in latest_sql

    assert repository.get_latest_rejected(task_id) is None
    rejected_sql = _executed_sql(session)
    assert "task_completion_reviews.review_status = 'rejected'" in rejected_sql
    assert (
        "ORDER BY task_completion_reviews.review_round DESC, "
        "task_completion_reviews.submitted_at DESC, "
        "task_completion_reviews.completion_review_id DESC" in rejected_sql
    )
    assert "LIMIT 1" in rejected_sql


def test_task_timeline_is_paginated_counted_and_rounds_are_read_only() -> None:
    task_id = uuid4()
    session = _session_with_result()
    repository = TaskCompletionReviewRepository(session)

    assert repository.list_by_task_id(task_id, limit=20, offset=10) == []
    timeline_sql = _executed_sql(session)
    assert f"task_completion_reviews.task_id = '{task_id}'" in timeline_sql
    assert (
        "ORDER BY task_completion_reviews.review_round DESC, "
        "task_completion_reviews.submitted_at DESC, "
        "task_completion_reviews.completion_review_id DESC" in timeline_sql
    )
    assert "LIMIT 20 OFFSET 10" in timeline_sql

    session.execute.return_value.scalar_one.return_value = 4
    assert repository.count_by_task_id(task_id) == 4
    count_sql = _executed_sql(session)
    assert "count(*)" in count_sql
    assert f"task_completion_reviews.task_id = '{task_id}'" in count_sql

    session.execute.return_value.scalar_one.return_value = 3
    assert repository.max_round(task_id) == 3
    max_sql = _executed_sql(session)
    assert "coalesce(max(task_completion_reviews.review_round), 0)" in max_sql
    assert f"task_completion_reviews.task_id = '{task_id}'" in max_sql
    assert "FOR UPDATE" not in max_sql

    repository.max_round = MagicMock(return_value=3)
    assert repository.next_round(task_id) == 4
    repository.max_round.assert_called_once_with(task_id)


def test_reviewer_candidate_queries_are_bounded_and_exclude_stale_rework() -> None:
    session = _session_with_result()
    repository = TaskCompletionReviewRepository(session)

    assert repository.list_submitted_for_reviewer("E002", limit=25) == []
    submitted_sql = _executed_sql(session)
    assert "task_completion_reviews.reviewer_employee_no = 'E002'" in submitted_sql
    assert "task_completion_reviews.review_status = 'submitted'" in submitted_sql
    assert (
        "ORDER BY task_completion_reviews.submitted_at DESC, "
        "task_completion_reviews.completion_review_id DESC" in submitted_sql
    )
    assert "LIMIT 25" in submitted_sql

    assert (
        repository.list_rejected_rework_candidates_for_reviewer(
            "E002",
            limit=30,
        )
        == []
    )
    rejected_sql = _executed_sql(session)
    assert "task_completion_reviews.reviewer_employee_no = 'E002'" in rejected_sql
    assert "task_completion_reviews.review_status = 'rejected'" in rejected_sql
    assert "task_completion_reviews.rework_node_id IS NOT NULL" in rejected_sql
    assert "SELECT max(task_completion_reviews_1.review_round)" in rejected_sql
    assert (
        "task_completion_reviews_1.task_id = "
        "task_completion_reviews.task_id" in rejected_sql
    )
    assert "task_completion_reviews.review_round = (SELECT" in rejected_sql
    assert "LIMIT 30" in rejected_sql
