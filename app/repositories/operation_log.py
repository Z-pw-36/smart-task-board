"""
Feature: Task detail read-only operation audit projection.

Responsibilities:
- Load operation audit rows for an already authorized task detail read.
- Keep task-scoped audit ordering consistent for DEV-05 views.

Does not own: audit writes, administrator audit search, or permission decisions.
Plan task: DEV-05.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OperationLog


class OperationLogRepository:
    """Read operation logs by business object for task detail projections."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_object(
        self,
        *,
        object_type: str,
        object_id: UUID | str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OperationLog]:
        statement = (
            select(OperationLog)
            .where(
                OperationLog.object_type == object_type,
                OperationLog.object_id == str(object_id),
            )
            .order_by(OperationLog.created_at.desc(), OperationLog.operation_log_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement).all())
