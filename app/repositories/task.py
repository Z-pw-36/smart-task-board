from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task, TaskParticipant


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
