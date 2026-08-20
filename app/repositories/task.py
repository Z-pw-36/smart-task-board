from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, exists, false, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Task,
    TaskCompletionReview,
    TaskIssue,
    TaskNode,
    TaskNodeParticipant,
    TaskParticipant,
)


class TaskRepository:
    """Persistence operations for tasks and task-level participants."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, task: Task) -> Task:
        self.session.add(task)
        self.session.flush()
        return task

    def get_by_id(self, task_id: UUID) -> Task | None:
        statement = select(Task).where(Task.task_id == task_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_id_for_update(self, task_id: UUID) -> Task | None:
        statement = select(Task).where(Task.task_id == task_id).with_for_update()
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_task_no(self, task_no: str) -> Task | None:
        statement = select(Task).where(Task.task_no == task_no)
        return self.session.execute(statement).scalar_one_or_none()

    def list_created_by(self, employee_no: str) -> list[Task]:
        statement = (
            select(Task)
            .where(Task.creator_employee_no == employee_no)
            .order_by(Task.created_at.desc(), Task.task_id)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_assigned_to(self, employee_no: str) -> list[Task]:
        statement = (
            select(Task)
            .where(Task.main_assignee_employee_no == employee_no)
            .order_by(Task.created_at.desc(), Task.task_id)
        )
        return list(self.session.execute(statement).scalars().all())

    @staticmethod
    def _participating_predicate(employee_no: str):
        return or_(
            Task.report_to_employee_no == employee_no,
            Task.reviewer_employee_no == employee_no,
            exists().where(
                TaskParticipant.task_id == Task.task_id,
                TaskParticipant.employee_no == employee_no,
            ),
            exists().where(
                TaskNode.task_id == Task.task_id,
                TaskNode.owner_employee_no == employee_no,
            ),
            exists().where(
                TaskNodeParticipant.task_id == Task.task_id,
                TaskNodeParticipant.employee_no == employee_no,
            ),
            exists().where(
                TaskIssue.task_id == Task.task_id,
                or_(
                    TaskIssue.reported_by_employee_no == employee_no,
                    TaskIssue.owner_employee_no == employee_no,
                ),
            ),
            exists().where(
                TaskCompletionReview.task_id == Task.task_id,
                or_(
                    TaskCompletionReview.submitted_by_employee_no
                    == employee_no,
                    TaskCompletionReview.reviewer_employee_no
                    == employee_no,
                ),
            ),
        )

    @classmethod
    def _related_predicate(cls, employee_no: str):
        return or_(
            Task.creator_employee_no == employee_no,
            Task.main_assignee_employee_no == employee_no,
            cls._participating_predicate(employee_no),
        )

    @classmethod
    def _relation_predicate(cls, employee_no: str, relation: str):
        if relation == "created":
            return Task.creator_employee_no == employee_no
        if relation == "assigned":
            return Task.main_assignee_employee_no == employee_no
        if relation == "participating":
            return cls._participating_predicate(employee_no)
        return cls._related_predicate(employee_no)

    @classmethod
    def _filtered_related_statement(
        cls,
        employee_no: str,
        *,
        relation: str = "all",
        task_status: str | None = None,
        search: str | None = None,
        deadline_from: datetime | None = None,
        deadline_to: datetime | None = None,
    ) -> Select[tuple[Task]]:
        statement = select(Task).where(cls._relation_predicate(employee_no, relation))
        if task_status is not None:
            statement = statement.where(Task.status == task_status)
        if search:
            statement = statement.where(Task.task_name.contains(search, autoescape=True))
        if deadline_from is not None:
            statement = statement.where(Task.deadline >= deadline_from)
        if deadline_to is not None:
            statement = statement.where(Task.deadline < deadline_to)
        return statement

    def list_related(
        self,
        employee_no: str,
        *,
        relation: str = "all",
        task_status: str | None = None,
        search: str | None = None,
        deadline_from: datetime | None = None,
        deadline_to: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Task], int]:
        filtered = self._filtered_related_statement(
            employee_no,
            relation=relation,
            task_status=task_status,
            search=search,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
        )
        count_statement = select(func.count()).select_from(filtered.subquery())
        total = self.session.execute(count_statement).scalar_one()
        statement = filtered.order_by(
            func.coalesce(Task.is_urgent, false()).desc(),
            Task.deadline.asc().nulls_last(),
            Task.created_at.desc(),
            Task.task_id,
        ).limit(limit).offset(offset)
        return list(self.session.execute(statement).scalars().all()), total

    def list_recent_related(self, employee_no: str, *, limit: int = 5) -> list[Task]:
        statement = (
            select(Task)
            .where(self._related_predicate(employee_no))
            .order_by(Task.updated_at.desc(), Task.task_id)
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_inbox_candidates(
        self,
        employee_no: str,
        *,
        limit: int = 500,
    ) -> list[Task]:
        node_owner = exists().where(
            TaskNode.task_id == Task.task_id,
            TaskNode.owner_employee_no == employee_no,
        )
        predicate = or_(
            and_(Task.status == "pending_confirmation", Task.creator_employee_no == employee_no),
            and_(
                Task.status == "pending_acceptance",
                Task.main_assignee_employee_no == employee_no,
            ),
            and_(Task.status == "returned", Task.creator_employee_no == employee_no),
            and_(
                Task.status == "in_progress",
                or_(Task.main_assignee_employee_no == employee_no, node_owner),
            ),
            and_(
                Task.status == "pending_review",
                or_(
                    Task.reviewer_employee_no == employee_no,
                    and_(
                        Task.reviewer_employee_no.is_(None),
                        Task.creator_employee_no == employee_no,
                    ),
                ),
            ),
        )
        statement = (
            select(Task)
            .where(predicate)
            .order_by(Task.updated_at.desc(), Task.task_id)
            .limit(limit)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_report_due_candidates(self, employee_no: str) -> list[Task]:
        statement = (
            select(Task)
            .where(
                Task.status == "in_progress",
                Task.main_assignee_employee_no == employee_no,
                Task.report_cycle.is_not(None),
                Task.accepted_at.is_not(None),
            )
            .order_by(Task.deadline.asc().nulls_last(), Task.task_id)
        )
        return list(self.session.execute(statement).scalars().all())

    def count_related(
        self,
        employee_no: str,
        *,
        relation: str = "all",
        task_status: str | None = None,
        deadline_from: datetime | None = None,
        deadline_to: datetime | None = None,
        exclude_completed: bool = False,
    ) -> int:
        statement = self._filtered_related_statement(
            employee_no,
            relation=relation,
            task_status=task_status,
            deadline_from=deadline_from,
            deadline_to=deadline_to,
        )
        if exclude_completed:
            statement = statement.where(Task.status != "completed")
        return self.session.execute(
            select(func.count()).select_from(statement.subquery())
        ).scalar_one()

    def is_related(self, task_id: UUID, employee_no: str) -> bool:
        statement = select(
            exists().where(
                Task.task_id == task_id,
                self._related_predicate(employee_no),
            )
        )
        return bool(self.session.execute(statement).scalar_one())

    def add_participant(self, participant: TaskParticipant) -> TaskParticipant:
        self.session.add(participant)
        self.session.flush()
        return participant

    def get_participant(self, participant_id: UUID) -> TaskParticipant | None:
        statement = select(TaskParticipant).where(
            TaskParticipant.participant_id == participant_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_participants(self, task_id: UUID) -> list[TaskParticipant]:
        statement = (
            select(TaskParticipant)
            .where(TaskParticipant.task_id == task_id)
            .order_by(
                TaskParticipant.participant_role,
                TaskParticipant.employee_no,
                TaskParticipant.participant_id,
            )
        )
        return list(self.session.execute(statement).scalars().all())

    def find_participant(
        self,
        task_id: UUID,
        employee_no: str,
        participant_role: str,
    ) -> TaskParticipant | None:
        statement = select(TaskParticipant).where(
            TaskParticipant.task_id == task_id,
            TaskParticipant.employee_no == employee_no,
            TaskParticipant.participant_role == participant_role,
        )
        return self.session.execute(statement).scalar_one_or_none()
