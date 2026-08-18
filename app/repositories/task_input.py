from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TaskInput


class TaskInputRepository:
    """Persistence operations for original task submissions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, task_input: TaskInput) -> TaskInput:
        self.session.add(task_input)
        self.session.flush()
        return task_input

    def get_by_id(self, input_id: UUID) -> TaskInput | None:
        statement = select(TaskInput).where(TaskInput.input_id == input_id)
        return self.session.execute(statement).scalar_one_or_none()
