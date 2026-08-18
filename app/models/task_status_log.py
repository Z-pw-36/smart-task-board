from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskStatusLog(Base):
    """Append-only history of successful task lifecycle events."""

    __tablename__ = "task_status_logs"
    __table_args__ = (
        CheckConstraint(
            "task_version >= 1",
            name="ck_task_status_logs_task_version_positive",
        ),
        CheckConstraint(
            "(business_ref_type IS NULL AND business_ref_id IS NULL) "
            "OR (business_ref_type IS NOT NULL AND business_ref_id IS NOT NULL)",
            name="ck_task_status_logs_business_ref_pair",
        ),
        Index(
            "ix_task_status_logs_task_timeline",
            "task_id",
            "created_at",
            "status_log_id",
        ),
        Index(
            "ix_task_status_logs_business_ref",
            "business_ref_type",
            "business_ref_id",
        ),
    )

    status_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String, nullable=True)
    to_status: Mapped[str] = mapped_column(String, nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    operator_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    target_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    task_version: Mapped[int] = mapped_column(Integer, nullable=False)
    business_ref_type: Mapped[str | None] = mapped_column(String, nullable=True)
    business_ref_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    operation_source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    task: Mapped[Task] = relationship(
        back_populates="status_logs",
        foreign_keys=[task_id],
    )
    operator: Mapped[User | None] = relationship(
        back_populates="operated_task_status_logs",
        foreign_keys=[operator_employee_no],
    )
    target_employee: Mapped[User | None] = relationship(
        back_populates="targeted_task_status_logs",
        foreign_keys=[target_employee_no],
    )
