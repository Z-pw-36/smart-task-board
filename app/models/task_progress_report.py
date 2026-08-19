from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.task_issue import TaskIssue
    from app.models.task_node import TaskNode
    from app.models.user import User


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskProgressReport(Base):
    """Immutable progress fact reported for a task or one of its nodes."""

    __tablename__ = "task_progress_reports"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "progress_report_id",
            name="uq_task_progress_reports_task_report",
        ),
        ForeignKeyConstraint(
            ["task_id", "node_id"],
            ["task_nodes.task_id", "task_nodes.node_id"],
            ondelete="RESTRICT",
            name="fk_task_progress_reports_node_same_task",
        ),
        ForeignKeyConstraint(
            ["task_id", "corrects_report_id"],
            [
                "task_progress_reports.task_id",
                "task_progress_reports.progress_report_id",
            ],
            ondelete="RESTRICT",
            name="fk_task_progress_reports_corrected_report_same_task",
        ),
        CheckConstraint(
            "progress_percent BETWEEN 0 AND 100",
            name="ck_task_progress_reports_progress_percent_range",
        ),
        CheckConstraint(
            "btrim(report_content) <> ''",
            name="ck_task_progress_reports_content_non_blank",
        ),
        CheckConstraint(
            "actual_hours IS NULL OR actual_hours >= 0",
            name="ck_task_progress_reports_actual_hours_non_negative",
        ),
        CheckConstraint(
            "corrects_report_id IS NULL "
            "OR corrects_report_id <> progress_report_id",
            name="ck_task_progress_reports_not_self_correction",
        ),
        CheckConstraint(
            "(report_period_start IS NULL AND report_period_end IS NULL) "
            "OR (report_period_start IS NOT NULL AND report_period_end IS NOT NULL)",
            name="ck_task_progress_reports_period_pair",
        ),
        CheckConstraint(
            "report_period_start IS NULL "
            "OR report_period_end > report_period_start",
            name="ck_task_progress_reports_period_order",
        ),
        CheckConstraint(
            "node_id IS NULL "
            "OR (report_period_start IS NULL AND report_period_end IS NULL)",
            name="ck_task_progress_reports_node_period_absent",
        ),
        CheckConstraint(
            "task_version >= 1",
            name="ck_task_progress_reports_task_version_positive",
        ),
        CheckConstraint(
            "btrim(operation_source) <> ''",
            name="ck_task_progress_reports_operation_source_non_blank",
        ),
        Index(
            "uq_task_progress_reports_one_current_task_period",
            "task_id",
            "report_period_end",
            unique=True,
            postgresql_where=text(
                "node_id IS NULL "
                "AND corrects_report_id IS NULL "
                "AND report_period_end IS NOT NULL"
            ),
        ),
        Index(
            "ix_task_progress_reports_task_timeline",
            "task_id",
            "created_at",
            "progress_report_id",
        ),
        Index(
            "ix_task_progress_reports_node_timeline",
            "task_id",
            "node_id",
            "created_at",
            "progress_report_id",
        ),
        Index(
            "ix_task_progress_reports_reporter_timeline",
            "reporter_employee_no",
            "created_at",
        ),
        Index(
            "ix_task_progress_reports_corrects_report_id",
            "corrects_report_id",
        ),
    )

    progress_report_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    reporter_employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    report_content: Mapped[str] = mapped_column(String, nullable=False)
    stage_result: Mapped[str | None] = mapped_column(String, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String, nullable=True)
    resource_request: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_hours: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    corrects_report_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    report_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    report_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    task_version: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    task: Mapped[Task] = relationship(
        back_populates="progress_reports",
        foreign_keys=[task_id],
    )
    node: Mapped[TaskNode | None] = relationship(
        back_populates="progress_reports",
        primaryjoin=(
            "and_(TaskNode.task_id == foreign(TaskProgressReport.task_id), "
            "TaskNode.node_id == foreign(TaskProgressReport.node_id))"
        ),
        foreign_keys=[task_id, node_id],
        viewonly=True,
    )
    reporter: Mapped[User] = relationship(
        back_populates="submitted_progress_reports",
        foreign_keys=[reporter_employee_no],
    )
    corrects_report: Mapped[TaskProgressReport | None] = relationship(
        back_populates="corrections",
        foreign_keys=[task_id, corrects_report_id],
        remote_side=[task_id, progress_report_id],
        viewonly=True,
    )
    corrections: Mapped[list[TaskProgressReport]] = relationship(
        back_populates="corrects_report",
        foreign_keys=[task_id, corrects_report_id],
        viewonly=True,
    )
    issues: Mapped[list[TaskIssue]] = relationship(
        back_populates="source_progress_report",
        primaryjoin=(
            "and_(TaskProgressReport.task_id == foreign(TaskIssue.task_id), "
            "TaskProgressReport.progress_report_id == "
            "foreign(TaskIssue.source_progress_report_id))"
        ),
        foreign_keys="[TaskIssue.task_id, TaskIssue.source_progress_report_id]",
        viewonly=True,
    )
