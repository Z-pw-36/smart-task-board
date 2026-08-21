from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TaskChangeRequest


class TaskChangeRequestRepository:
    """Append-only persistence and stable change-request queries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, request: TaskChangeRequest) -> TaskChangeRequest:
        self.session.add(request)
        self.session.flush()
        return request

    def get_by_id(self, change_request_id: UUID) -> TaskChangeRequest | None:
        statement = select(TaskChangeRequest).where(
            TaskChangeRequest.change_request_id == change_request_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    # Useful for decision handlers that already hold and validate the task
    # lock; task-scoped callers should prefer ``get_by_task_and_id_for_update``.
    def get_by_id_for_update(
        self,
        change_request_id: UUID,
    ) -> TaskChangeRequest | None:
        statement = (
            select(TaskChangeRequest)
            .where(TaskChangeRequest.change_request_id == change_request_id)
            .with_for_update()
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_task_and_id_for_update(
        self,
        task_id: UUID,
        change_request_id: UUID,
    ) -> TaskChangeRequest | None:
        statement = (
            select(TaskChangeRequest)
            .where(
                TaskChangeRequest.task_id == task_id,
                TaskChangeRequest.change_request_id == change_request_id,
            )
            .with_for_update()
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_pending(self, task_id: UUID) -> TaskChangeRequest | None:
        statement = select(TaskChangeRequest).where(
            TaskChangeRequest.task_id == task_id,
            TaskChangeRequest.status == "pending",
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_pending_for_update(self, task_id: UUID) -> TaskChangeRequest | None:
        statement = (
            select(TaskChangeRequest)
            .where(
                TaskChangeRequest.task_id == task_id,
                TaskChangeRequest.status == "pending",
            )
            .with_for_update()
        )
        return self.session.execute(statement).scalar_one_or_none()

    # A descriptive alias used by callers that prefer the status in the name.
    get_current_pending = get_pending
    get_current_pending_for_update = get_pending_for_update

    def list_by_task_id(
        self,
        task_id: UUID,
        *,
        status: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[TaskChangeRequest]:
        statement = select(TaskChangeRequest).where(
            TaskChangeRequest.task_id == task_id
        )
        if status is not None:
            statement = statement.where(TaskChangeRequest.status == status)
        statement = (
            statement.order_by(
                TaskChangeRequest.created_at.desc(),
                TaskChangeRequest.change_request_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(statement).scalars().all())

    def count_by_task_id(
        self,
        task_id: UUID,
        *,
        status: str | None = None,
    ) -> int:
        statement = select(func.count()).select_from(TaskChangeRequest).where(
            TaskChangeRequest.task_id == task_id
        )
        if status is not None:
            statement = statement.where(TaskChangeRequest.status == status)
        return self.session.execute(statement).scalar_one()

    def list_pending(self, *, limit: int = 500, offset: int = 0) -> list[TaskChangeRequest]:
        statement = (
            select(TaskChangeRequest)
            .where(TaskChangeRequest.status == "pending")
            .order_by(
                TaskChangeRequest.created_at,
                TaskChangeRequest.change_request_id,
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_requester(
        self,
        requester_employee_no: str,
        *,
        status: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[TaskChangeRequest]:
        statement = select(TaskChangeRequest).where(
            TaskChangeRequest.requester_employee_no == requester_employee_no
        )
        if status is not None:
            statement = statement.where(TaskChangeRequest.status == status)
        statement = (
            statement.order_by(
                TaskChangeRequest.created_at.desc(),
                TaskChangeRequest.change_request_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(statement).scalars().all())

    # Keep the role-oriented name available for queue implementations.
    list_pending_for_approval = list_pending
    list_pending_for_reviewer = list_pending
