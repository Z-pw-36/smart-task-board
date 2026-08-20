from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import TaskIssue

ACTIVE_ISSUE_STATUSES = ("open", "processing")


class TaskIssueRepository:
    """Persistence and lifecycle queries for task issues."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, issue: TaskIssue) -> TaskIssue:
        self.session.add(issue)
        self.session.flush()
        return issue

    def get_by_id(self, issue_id: UUID) -> TaskIssue | None:
        statement = select(TaskIssue).where(TaskIssue.issue_id == issue_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_task_and_id_for_update(
        self,
        task_id: UUID,
        issue_id: UUID,
    ) -> TaskIssue | None:
        statement = (
            select(TaskIssue)
            .where(TaskIssue.task_id == task_id, TaskIssue.issue_id == issue_id)
            .with_for_update()
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_task_id(
        self,
        task_id: UUID,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> list[TaskIssue]:
        statement = select(TaskIssue).where(TaskIssue.task_id == task_id)
        if status is not None:
            statement = statement.where(TaskIssue.status == status)
        statement = statement.order_by(
            TaskIssue.created_at.desc(),
            TaskIssue.issue_id.desc(),
        ).limit(limit).offset(offset)
        return list(self.session.execute(statement).scalars().all())

    def count_by_task_id(self, task_id: UUID, *, status: str | None) -> int:
        statement = select(func.count()).select_from(TaskIssue).where(
            TaskIssue.task_id == task_id
        )
        if status is not None:
            statement = statement.where(TaskIssue.status == status)
        return self.session.execute(statement).scalar_one()

    def has_active_blocker(self, task_id: UUID, node_id: UUID) -> bool:
        statement = select(
            select(TaskIssue.issue_id)
            .where(
                TaskIssue.task_id == task_id,
                TaskIssue.node_id == node_id,
                TaskIssue.issue_type == "blocker",
                TaskIssue.status.in_(ACTIVE_ISSUE_STATUSES),
            )
            .exists()
        )
        return bool(self.session.execute(statement).scalar_one())

    def has_non_closed(self, task_id: UUID) -> bool:
        statement = select(
            select(TaskIssue.issue_id)
            .where(
                TaskIssue.task_id == task_id,
                TaskIssue.status != "closed",
            )
            .exists()
        )
        return bool(self.session.execute(statement).scalar_one())

    def count_open_owned_by(self, employee_no: str) -> int:
        statement = select(func.count()).select_from(TaskIssue).where(
            TaskIssue.owner_employee_no == employee_no,
            TaskIssue.status.in_(ACTIVE_ISSUE_STATUSES),
        )
        return self.session.execute(statement).scalar_one()

    def list_actionable_for(self, employee_no: str) -> list[TaskIssue]:
        statement = (
            select(TaskIssue)
            .where(
                or_(
                    and_(
                        TaskIssue.owner_employee_no == employee_no,
                        TaskIssue.status.in_(ACTIVE_ISSUE_STATUSES),
                    ),
                    and_(
                        TaskIssue.reported_by_employee_no == employee_no,
                        TaskIssue.status.in_(("resolved", "rejected")),
                    ),
                )
            )
            .order_by(TaskIssue.created_at.desc(), TaskIssue.issue_id.desc())
        )
        return list(self.session.execute(statement).scalars().all())

    def has_employee_relation(self, task_id: UUID, employee_no: str) -> bool:
        statement = select(
            select(TaskIssue.issue_id)
            .where(
                TaskIssue.task_id == task_id,
                or_(
                    TaskIssue.reported_by_employee_no == employee_no,
                    TaskIssue.owner_employee_no == employee_no,
                ),
            )
            .exists()
        )
        return bool(self.session.execute(statement).scalar_one())
