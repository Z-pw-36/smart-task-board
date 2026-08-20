from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models import TaskCompletionReview


class TaskCompletionReviewRepository:
    """Append-oriented persistence and stable completion-review queries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, review: TaskCompletionReview) -> TaskCompletionReview:
        self.session.add(review)
        self.session.flush()
        return review

    def get_by_id(
        self,
        completion_review_id: UUID,
    ) -> TaskCompletionReview | None:
        statement = select(TaskCompletionReview).where(
            TaskCompletionReview.completion_review_id
            == completion_review_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_task_and_id_for_update(
        self,
        task_id: UUID,
        completion_review_id: UUID,
    ) -> TaskCompletionReview | None:
        statement = (
            select(TaskCompletionReview)
            .where(
                TaskCompletionReview.task_id == task_id,
                TaskCompletionReview.completion_review_id
                == completion_review_id,
            )
            .with_for_update()
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_current_submitted(
        self,
        task_id: UUID,
    ) -> TaskCompletionReview | None:
        statement = select(TaskCompletionReview).where(
            TaskCompletionReview.task_id == task_id,
            TaskCompletionReview.review_status == "submitted",
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_latest(self, task_id: UUID) -> TaskCompletionReview | None:
        statement = (
            select(TaskCompletionReview)
            .where(TaskCompletionReview.task_id == task_id)
            .order_by(
                TaskCompletionReview.review_round.desc(),
                TaskCompletionReview.submitted_at.desc(),
                TaskCompletionReview.completion_review_id.desc(),
            )
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_latest_rejected(
        self,
        task_id: UUID,
    ) -> TaskCompletionReview | None:
        statement = (
            select(TaskCompletionReview)
            .where(
                TaskCompletionReview.task_id == task_id,
                TaskCompletionReview.review_status == "rejected",
            )
            .order_by(
                TaskCompletionReview.review_round.desc(),
                TaskCompletionReview.submitted_at.desc(),
                TaskCompletionReview.completion_review_id.desc(),
            )
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_task_id(
        self,
        task_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[TaskCompletionReview]:
        statement = (
            select(TaskCompletionReview)
            .where(TaskCompletionReview.task_id == task_id)
            .order_by(
                TaskCompletionReview.review_round.desc(),
                TaskCompletionReview.submitted_at.desc(),
                TaskCompletionReview.completion_review_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(statement).scalars().all())

    def count_by_task_id(self, task_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(TaskCompletionReview)
            .where(TaskCompletionReview.task_id == task_id)
        )
        return self.session.execute(statement).scalar_one()

    def max_round(self, task_id: UUID) -> int:
        statement = select(
            func.coalesce(func.max(TaskCompletionReview.review_round), 0)
        ).where(TaskCompletionReview.task_id == task_id)
        return int(self.session.execute(statement).scalar_one())

    def next_round(self, task_id: UUID) -> int:
        """Return the next round after the caller has locked the task row."""
        return self.max_round(task_id) + 1

    def list_submitted_for_reviewer(
        self,
        employee_no: str,
        *,
        limit: int = 500,
    ) -> list[TaskCompletionReview]:
        statement = (
            select(TaskCompletionReview)
            .where(
                TaskCompletionReview.reviewer_employee_no == employee_no,
                TaskCompletionReview.review_status == "submitted",
            )
            .order_by(
                TaskCompletionReview.submitted_at.desc(),
                TaskCompletionReview.completion_review_id.desc(),
            )
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_rejected_rework_candidates_for_reviewer(
        self,
        employee_no: str,
        *,
        limit: int = 500,
    ) -> list[TaskCompletionReview]:
        other_review = aliased(TaskCompletionReview)
        latest_round = (
            select(func.max(other_review.review_round))
            .where(other_review.task_id == TaskCompletionReview.task_id)
            .correlate(TaskCompletionReview)
            .scalar_subquery()
        )
        statement = (
            select(TaskCompletionReview)
            .where(
                TaskCompletionReview.reviewer_employee_no == employee_no,
                TaskCompletionReview.review_status == "rejected",
                TaskCompletionReview.rework_node_id.is_not(None),
                TaskCompletionReview.review_round == latest_round,
            )
            .order_by(
                TaskCompletionReview.reviewed_at.desc().nulls_last(),
                TaskCompletionReview.completion_review_id.desc(),
            )
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())
