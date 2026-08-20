from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.task_node import TaskNode
    from app.models.user import User


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskCompletionReview(Base):
    """One completion-submission round and its one-time review decision."""

    __tablename__ = "task_completion_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "rework_node_id"],
            ["task_nodes.task_id", "task_nodes.node_id"],
            ondelete="RESTRICT",
            name="fk_task_completion_reviews_rework_node_same_task",
        ),
        UniqueConstraint(
            "task_id",
            "review_round",
            name="uq_task_completion_reviews_task_round",
        ),
        CheckConstraint(
            "review_round >= 1",
            name="ck_task_completion_reviews_review_round_positive",
        ),
        CheckConstraint(
            "submitted_task_version >= 1",
            name="ck_task_completion_reviews_submitted_version_positive",
        ),
        CheckConstraint(
            "review_status IN ('submitted', 'approved', 'rejected')",
            name="ck_task_completion_reviews_review_status_allowed",
        ),
        CheckConstraint(
            "review_result IS NULL "
            "OR review_result IN ('approved', 'rejected')",
            name="ck_task_completion_reviews_review_result_allowed",
        ),
        CheckConstraint(
            "completion_note IS NULL OR btrim(completion_note) <> ''",
            name="ck_task_completion_reviews_completion_note_non_blank",
        ),
        CheckConstraint(
            "deliverable_summary IS NULL OR btrim(deliverable_summary) <> ''",
            name=(
                "ck_task_completion_reviews_deliverable_summary_non_blank"
            ),
        ),
        CheckConstraint(
            "is_legacy_import "
            "OR (completion_note IS NOT NULL "
            "AND deliverable_summary IS NOT NULL)",
            name="ck_task_completion_reviews_nonlegacy_content_present",
        ),
        CheckConstraint(
            "(review_status = 'submitted' "
            "AND review_result IS NULL "
            "AND reject_reason IS NULL "
            "AND rework_node_id IS NULL "
            "AND reviewed_at IS NULL "
            "AND reviewed_task_version IS NULL) "
            "OR (review_status = 'approved' "
            "AND review_result = 'approved' "
            "AND reject_reason IS NULL "
            "AND rework_node_id IS NULL "
            "AND reviewed_at IS NOT NULL "
            "AND reviewed_at >= submitted_at "
            "AND reviewed_task_version IS NOT NULL "
            "AND reviewed_task_version > submitted_task_version) "
            "OR (review_status = 'rejected' "
            "AND review_result = 'rejected' "
            "AND reject_reason IS NOT NULL "
            "AND btrim(reject_reason) <> '' "
            "AND reviewed_at IS NOT NULL "
            "AND reviewed_at >= submitted_at "
            "AND reviewed_task_version IS NOT NULL "
            "AND reviewed_task_version > submitted_task_version)",
            name="ck_task_completion_reviews_lifecycle_fields",
        ),
        Index(
            "uq_task_completion_reviews_one_submitted_per_task",
            "task_id",
            unique=True,
            postgresql_where=text("review_status = 'submitted'"),
        ),
        Index(
            "ix_task_completion_reviews_task_timeline",
            "task_id",
            "review_round",
            "submitted_at",
            "completion_review_id",
        ),
        Index(
            "ix_task_completion_reviews_reviewer_status_timeline",
            "reviewer_employee_no",
            "review_status",
            "submitted_at",
            "completion_review_id",
        ),
        Index(
            "ix_task_completion_reviews_submitter_timeline",
            "submitted_by_employee_no",
            "submitted_at",
            "completion_review_id",
        ),
        Index(
            "ix_task_completion_reviews_rework_node",
            "task_id",
            "rework_node_id",
        ),
    )

    completion_review_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    review_round: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_by_employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
    )
    completion_note: Mapped[str | None] = mapped_column(String, nullable=True)
    deliverable_summary: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    reviewer_employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="submitted",
    )
    review_result: Mapped[str | None] = mapped_column(String, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    rework_node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    submitted_task_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    reviewed_task_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_legacy_import: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    task: Mapped[Task] = relationship(
        back_populates="completion_reviews",
        foreign_keys=[task_id],
    )
    submitted_by: Mapped[User] = relationship(
        back_populates="submitted_completion_reviews",
        foreign_keys=[submitted_by_employee_no],
    )
    reviewer: Mapped[User] = relationship(
        back_populates="assigned_completion_reviews",
        foreign_keys=[reviewer_employee_no],
    )
    rework_node: Mapped[TaskNode | None] = relationship(
        back_populates="rework_completion_reviews",
        primaryjoin=(
            "and_(TaskNode.task_id == foreign(TaskCompletionReview.task_id), "
            "TaskNode.node_id == "
            "foreign(TaskCompletionReview.rework_node_id))"
        ),
        foreign_keys=[task_id, rework_node_id],
        viewonly=True,
    )
