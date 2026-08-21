from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskChangeRequest(Base):
    """An immutable proposed task mutation and its eventual decision.

    A request captures the task state and requested patch at submission time.
    Services are responsible for applying a decision atomically; this model
    keeps the persisted lifecycle internally consistent so old requests remain
    useful audit records.
    """

    __tablename__ = "task_change_requests"
    __table_args__ = (
        CheckConstraint(
            "btrim(reason) <> ''",
            name="ck_task_change_requests_reason_non_blank",
        ),
        CheckConstraint(
            "jsonb_typeof(patch_json) = 'object' AND patch_json <> '{}'::jsonb",
            name="ck_task_change_requests_patch_object_non_empty",
        ),
        CheckConstraint(
            "requester_task_version >= 1",
            name="ck_task_change_requests_requester_task_version_positive",
        ),
        CheckConstraint(
            "base_task_version >= 1",
            name="ck_task_change_requests_base_task_version_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_task_change_requests_status_allowed",
        ),
        CheckConstraint(
            "(status = 'pending' "
            "AND decision_by_employee_no IS NULL "
            "AND decision_at IS NULL "
            "AND decision_comment IS NULL "
            "AND cancelled_by_employee_no IS NULL "
            "AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) "
            "OR (status = 'approved' "
            "AND decision_by_employee_no IS NOT NULL "
            "AND decision_at IS NOT NULL "
            "AND cancelled_by_employee_no IS NULL "
            "AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) "
            "OR (status = 'rejected' "
            "AND decision_by_employee_no IS NOT NULL "
            "AND decision_at IS NOT NULL "
            "AND decision_comment IS NOT NULL "
            "AND btrim(decision_comment) <> '' "
            "AND cancelled_by_employee_no IS NULL "
            "AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) "
            "OR (status = 'cancelled' "
            "AND cancelled_by_employee_no IS NOT NULL "
            "AND cancelled_at IS NOT NULL "
            "AND cancellation_reason IS NOT NULL "
            "AND btrim(cancellation_reason) <> '' "
            "AND decision_by_employee_no IS NULL "
            "AND decision_at IS NULL "
            "AND decision_comment IS NULL)",
            name="ck_task_change_requests_lifecycle_fields",
        ),
        Index(
            "ix_task_change_requests_task_timeline",
            "task_id",
            "created_at",
            "change_request_id",
        ),
        Index(
            "ix_task_change_requests_task_status_timeline",
            "task_id",
            "status",
            "created_at",
            "change_request_id",
        ),
        Index(
            "ix_task_change_requests_requester_timeline",
            "requester_employee_no",
            "created_at",
            "change_request_id",
        ),
        Index(
            "ix_task_change_requests_status_timeline",
            "status",
            "created_at",
            "change_request_id",
        ),
        Index(
            "uq_task_change_requests_one_pending_per_task",
            "task_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    change_request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    requester_employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
    )
    patch_json: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String, nullable=False)
    before_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    after_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
    )
    requester_task_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    base_task_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    decision_by_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
    )
    decision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decision_comment: Mapped[str | None] = mapped_column(String, nullable=True)
    cancelled_by_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    task: Mapped[Task] = relationship(
        back_populates="change_requests",
        foreign_keys=[task_id],
    )
    requester: Mapped[User] = relationship(
        back_populates="submitted_change_requests",
        foreign_keys=[requester_employee_no],
    )
    decision_by: Mapped[User | None] = relationship(
        back_populates="decided_change_requests",
        foreign_keys=[decision_by_employee_no],
    )
    cancelled_by: Mapped[User | None] = relationship(
        back_populates="cancelled_change_requests",
        foreign_keys=[cancelled_by_employee_no],
    )

    @property
    def requested_by_employee_no(self) -> str:
        return self.requester_employee_no

    @property
    def change_fields_json(self) -> dict[str, object]:
        return self.patch_json

    @property
    def change_reason(self) -> str:
        return self.reason

    @property
    def approval_status(self) -> str:
        return self.status

    @property
    def approved_by_employee_no(self) -> str | None:
        return self.decision_by_employee_no

    @property
    def approval_comment(self) -> str | None:
        return self.decision_comment

    @property
    def approved_at(self) -> datetime | None:
        return self.decision_at
