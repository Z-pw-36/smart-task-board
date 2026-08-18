from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class TaskParticipant(Base):
    """Employee participation and confirmation state within a task."""

    __tablename__ = "task_participants"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "employee_no",
            "participant_role",
            name="uq_task_participants_task_employee_role",
        ),
        CheckConstraint(
            "NOT is_primary OR participant_role = 'assignee'",
            name="ck_task_participants_primary_is_assignee",
        ),
        Index(
            "uq_task_participants_one_primary_assignee",
            "task_id",
            unique=True,
            postgresql_where=text(
                "participant_role = 'assignee' AND is_primary IS TRUE"
            ),
        ),
    )

    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    participant_role: Mapped[str] = mapped_column(String, nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    confirm_status: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    task: Mapped[Task] = relationship(
        back_populates="participants",
        foreign_keys=[task_id],
    )
    employee: Mapped[User] = relationship(
        back_populates="task_participations",
        foreign_keys=[employee_no],
    )
