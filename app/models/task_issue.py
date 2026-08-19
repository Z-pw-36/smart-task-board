from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.task_node import TaskNode
    from app.models.task_progress_report import TaskProgressReport
    from app.models.user import User


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskIssue(Base):
    """Blocker, resource need, collaboration request, or risk for a task."""

    __tablename__ = "task_issues"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "node_id"],
            ["task_nodes.task_id", "task_nodes.node_id"],
            ondelete="RESTRICT",
            name="fk_task_issues_node_same_task",
        ),
        ForeignKeyConstraint(
            ["task_id", "source_progress_report_id"],
            [
                "task_progress_reports.task_id",
                "task_progress_reports.progress_report_id",
            ],
            ondelete="RESTRICT",
            name="fk_task_issues_source_report_same_task",
        ),
        CheckConstraint(
            "issue_type IN "
            "('blocker', 'resource_request', 'collaboration_support', 'risk')",
            name="ck_task_issues_issue_type_allowed",
        ),
        CheckConstraint(
            "btrim(title) <> ''",
            name="ck_task_issues_title_non_blank",
        ),
        CheckConstraint(
            "btrim(description) <> ''",
            name="ck_task_issues_description_non_blank",
        ),
        CheckConstraint(
            "issue_type <> 'resource_request' "
            "OR (requested_resource IS NOT NULL "
            "AND btrim(requested_resource) <> '')",
            name="ck_task_issues_resource_request_requires_resource",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_task_issues_severity_allowed",
        ),
        CheckConstraint(
            "status IN ('open', 'processing', 'resolved', 'rejected', 'closed')",
            name="ck_task_issues_status_allowed",
        ),
        CheckConstraint(
            "status <> 'processing' OR processing_started_at IS NOT NULL",
            name="ck_task_issues_processing_started",
        ),
        CheckConstraint(
            "status <> 'resolved' "
            "OR (resolved_at IS NOT NULL "
            "AND resolved_by_employee_no IS NOT NULL "
            "AND resolution_note IS NOT NULL "
            "AND btrim(resolution_note) <> '')",
            name="ck_task_issues_resolved_fields",
        ),
        CheckConstraint(
            "status <> 'rejected' "
            "OR (rejected_at IS NOT NULL "
            "AND rejected_by_employee_no IS NOT NULL "
            "AND resolution_note IS NOT NULL "
            "AND btrim(resolution_note) <> '')",
            name="ck_task_issues_rejected_fields",
        ),
        CheckConstraint(
            "status <> 'closed' "
            "OR (closed_at IS NOT NULL "
            "AND closed_by_employee_no IS NOT NULL "
            "AND resolution_note IS NOT NULL "
            "AND btrim(resolution_note) <> '' "
            "AND ((resolved_at IS NOT NULL "
            "AND resolved_by_employee_no IS NOT NULL "
            "AND rejected_at IS NULL "
            "AND rejected_by_employee_no IS NULL) "
            "OR (rejected_at IS NOT NULL "
            "AND rejected_by_employee_no IS NOT NULL "
            "AND resolved_at IS NULL "
            "AND resolved_by_employee_no IS NULL)))",
            name="ck_task_issues_closed_fields",
        ),
        CheckConstraint(
            "status NOT IN ('open', 'processing') "
            "OR (resolved_at IS NULL "
            "AND rejected_at IS NULL "
            "AND closed_at IS NULL "
            "AND resolved_by_employee_no IS NULL "
            "AND rejected_by_employee_no IS NULL "
            "AND closed_by_employee_no IS NULL "
            "AND resolution_note IS NULL)",
            name="ck_task_issues_active_lifecycle_fields_absent",
        ),
        CheckConstraint(
            "status <> 'open' OR processing_started_at IS NULL",
            name="ck_task_issues_open_not_processing",
        ),
        CheckConstraint(
            "status <> 'resolved' "
            "OR (rejected_at IS NULL "
            "AND rejected_by_employee_no IS NULL "
            "AND closed_at IS NULL "
            "AND closed_by_employee_no IS NULL)",
            name="ck_task_issues_resolved_exclusive",
        ),
        CheckConstraint(
            "status <> 'rejected' "
            "OR (resolved_at IS NULL "
            "AND resolved_by_employee_no IS NULL "
            "AND closed_at IS NULL "
            "AND closed_by_employee_no IS NULL)",
            name="ck_task_issues_rejected_exclusive",
        ),
        Index(
            "ix_task_issues_task_timeline",
            "task_id",
            "created_at",
            "issue_id",
        ),
        Index(
            "ix_task_issues_task_status_timeline",
            "task_id",
            "status",
            "created_at",
            "issue_id",
        ),
        Index(
            "ix_task_issues_node_status",
            "task_id",
            "node_id",
            "status",
        ),
        Index(
            "ix_task_issues_owner_status_timeline",
            "owner_employee_no",
            "status",
            "created_at",
        ),
        Index(
            "ix_task_issues_source_progress_report_id",
            "source_progress_report_id",
        ),
        Index(
            "ix_task_issues_active_task_node",
            "task_id",
            "node_id",
            postgresql_where=text("status IN ('open', 'processing')"),
        ),
    )

    issue_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    node_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source_progress_report_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    reported_by_employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
    )
    issue_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    requested_resource: Mapped[str | None] = mapped_column(String, nullable=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    owner_employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
    )
    resolution_note: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_by_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
    )
    rejected_by_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
    )
    closed_by_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    task: Mapped[Task] = relationship(
        back_populates="issues",
        foreign_keys=[task_id],
    )
    node: Mapped[TaskNode | None] = relationship(
        back_populates="issues",
        primaryjoin=(
            "and_(TaskNode.task_id == foreign(TaskIssue.task_id), "
            "TaskNode.node_id == foreign(TaskIssue.node_id))"
        ),
        foreign_keys=[task_id, node_id],
        viewonly=True,
    )
    source_progress_report: Mapped[TaskProgressReport | None] = relationship(
        back_populates="issues",
        primaryjoin=(
            "and_(TaskProgressReport.task_id == foreign(TaskIssue.task_id), "
            "TaskProgressReport.progress_report_id == "
            "foreign(TaskIssue.source_progress_report_id))"
        ),
        foreign_keys=[task_id, source_progress_report_id],
        viewonly=True,
    )
    reported_by: Mapped[User] = relationship(
        back_populates="reported_task_issues",
        foreign_keys=[reported_by_employee_no],
    )
    owner: Mapped[User] = relationship(
        back_populates="owned_task_issues",
        foreign_keys=[owner_employee_no],
    )
    resolved_by: Mapped[User | None] = relationship(
        back_populates="resolved_task_issues",
        foreign_keys=[resolved_by_employee_no],
    )
    rejected_by: Mapped[User | None] = relationship(
        back_populates="rejected_task_issues",
        foreign_keys=[rejected_by_employee_no],
    )
    closed_by: Mapped[User | None] = relationship(
        back_populates="closed_task_issues",
        foreign_keys=[closed_by_employee_no],
    )
