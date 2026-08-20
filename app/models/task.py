from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ai_extraction_record import AIExtractionRecord
    from app.models.department import Department
    from app.models.task_completion_review import TaskCompletionReview
    from app.models.task_issue import TaskIssue
    from app.models.task_node import TaskNode
    from app.models.task_node_dependency import TaskNodeDependency
    from app.models.task_participant import TaskParticipant
    from app.models.task_progress_report import TaskProgressReport
    from app.models.task_status_log import TaskStatusLog
    from app.models.user import User


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Task(Base):
    """Confirmed task facts and current lifecycle state."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "estimated_hours IS NULL OR estimated_hours >= 0",
            name="ck_tasks_estimated_hours_non_negative",
        ),
        CheckConstraint(
            "actual_hours IS NULL OR actual_hours >= 0",
            name="ck_tasks_actual_hours_non_negative",
        ),
        CheckConstraint(
            "task_weight IS NULL OR task_weight BETWEEN 1 AND 5",
            name="ck_tasks_task_weight_range",
        ),
        CheckConstraint(
            "merged_into_task_id IS NULL OR merged_into_task_id <> task_id",
            name="ck_tasks_not_merged_into_self",
        ),
        CheckConstraint(
            "task_version >= 1",
            name="ck_tasks_task_version_positive",
        ),
        CheckConstraint(
            "report_cycle IS NULL OR report_cycle ~ "
            "'^weekly:(MON|TUE|WED|THU|FRI|SAT|SUN)@"
            "([01][0-9]|2[0-3]):[0-5][0-9]$'",
            name="ck_tasks_report_cycle_format",
        ),
    )

    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_no: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        unique=True,
    )
    task_name: Mapped[str] = mapped_column(String, nullable=False)
    task_description: Mapped[str | None] = mapped_column(String, nullable=True)
    task_goal: Mapped[str | None] = mapped_column(String, nullable=True)
    task_source: Mapped[str | None] = mapped_column(String, nullable=True)
    creator_employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    main_assignee_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    report_to_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    report_to_level: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.department_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="draft",
        index=True,
    )
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    actual_hours: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    task_weight: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deliverable: Mapped[str | None] = mapped_column(String, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(String, nullable=True)
    is_urgent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    report_cycle: Mapped[str | None] = mapped_column(String, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    withdraw_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    merged_into_task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    task_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    creator: Mapped[User] = relationship(
        back_populates="created_tasks",
        foreign_keys=[creator_employee_no],
    )
    main_assignee: Mapped[User | None] = relationship(
        back_populates="assigned_tasks",
        foreign_keys=[main_assignee_employee_no],
    )
    report_to: Mapped[User | None] = relationship(
        back_populates="reporting_tasks",
        foreign_keys=[report_to_employee_no],
    )
    reviewer: Mapped[User | None] = relationship(
        back_populates="review_tasks",
        foreign_keys=[reviewer_employee_no],
    )
    department: Mapped[Department | None] = relationship(
        back_populates="tasks",
        foreign_keys=[department_id],
    )
    participants: Mapped[list[TaskParticipant]] = relationship(
        back_populates="task",
        foreign_keys="TaskParticipant.task_id",
    )
    nodes: Mapped[list[TaskNode]] = relationship(
        back_populates="task",
        foreign_keys="TaskNode.task_id",
        order_by="(TaskNode.node_order, TaskNode.sort_weight, TaskNode.node_id)",
    )
    node_dependencies: Mapped[list[TaskNodeDependency]] = relationship(
        back_populates="task",
        foreign_keys="TaskNodeDependency.task_id",
    )
    status_logs: Mapped[list[TaskStatusLog]] = relationship(
        back_populates="task",
        foreign_keys="TaskStatusLog.task_id",
        order_by="(TaskStatusLog.created_at, TaskStatusLog.status_log_id)",
    )
    ai_extraction_records: Mapped[list[AIExtractionRecord]] = relationship(
        back_populates="task",
        foreign_keys="AIExtractionRecord.task_id",
    )
    progress_reports: Mapped[list[TaskProgressReport]] = relationship(
        back_populates="task",
        foreign_keys="TaskProgressReport.task_id",
        order_by=(
            "(TaskProgressReport.created_at, "
            "TaskProgressReport.progress_report_id)"
        ),
    )
    issues: Mapped[list[TaskIssue]] = relationship(
        back_populates="task",
        foreign_keys="TaskIssue.task_id",
        order_by="(TaskIssue.created_at, TaskIssue.issue_id)",
    )
    completion_reviews: Mapped[list[TaskCompletionReview]] = relationship(
        back_populates="task",
        foreign_keys="TaskCompletionReview.task_id",
        order_by=(
            "(TaskCompletionReview.review_round, "
            "TaskCompletionReview.completion_review_id)"
        ),
    )
    merged_into_task: Mapped[Task | None] = relationship(
        back_populates="merged_from_tasks",
        remote_side=[task_id],
        foreign_keys=[merged_into_task_id],
    )
    merged_from_tasks: Mapped[list[Task]] = relationship(
        back_populates="merged_into_task",
        foreign_keys=[merged_into_task_id],
    )
