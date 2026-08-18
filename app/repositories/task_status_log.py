from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TaskStatusLog


class TaskStatusLogRepository:
    """Append-only persistence and stable timeline queries for status logs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, status_log: TaskStatusLog) -> TaskStatusLog:
        self.session.add(status_log)
        self.session.flush()
        return status_log

    def get_by_id(self, status_log_id: UUID) -> TaskStatusLog | None:
        statement = select(TaskStatusLog).where(
            TaskStatusLog.status_log_id == status_log_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_task_id(self, task_id: UUID) -> list[TaskStatusLog]:
        statement = (
            select(TaskStatusLog)
            .where(TaskStatusLog.task_id == task_id)
            .order_by(TaskStatusLog.created_at, TaskStatusLog.status_log_id)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_task_id_paginated(
        self,
        task_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[TaskStatusLog]:
        statement = (
            select(TaskStatusLog)
            .where(TaskStatusLog.task_id == task_id)
            .order_by(TaskStatusLog.created_at, TaskStatusLog.status_log_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(statement).scalars().all())

    def count_by_task_id(self, task_id: UUID) -> int:
        statement = select(func.count()).select_from(TaskStatusLog).where(
            TaskStatusLog.task_id == task_id
        )
        return self.session.execute(statement).scalar_one()

    def get_latest_for_task(self, task_id: UUID) -> TaskStatusLog | None:
        statement = (
            select(TaskStatusLog)
            .where(TaskStatusLog.task_id == task_id)
            .order_by(
                TaskStatusLog.created_at.desc(),
                TaskStatusLog.status_log_id.desc(),
            )
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()
