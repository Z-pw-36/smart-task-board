from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.task_node_dependency import TaskNodeDependency
    from app.models.task_node_participant import TaskNodeParticipant
    from app.models.user import User


class TaskNode(Base):
    """One executable node within a task decomposition."""

    __tablename__ = "task_nodes"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "node_id",
            name="uq_task_nodes_task_node",
        ),
        CheckConstraint(
            "node_order >= 1",
            name="ck_task_nodes_node_order_positive",
        ),
        CheckConstraint(
            "planned_start_time IS NULL "
            "OR planned_deadline IS NULL "
            "OR planned_deadline >= planned_start_time",
            name="ck_task_nodes_planned_time_order",
        ),
        CheckConstraint(
            "estimated_hours IS NULL OR estimated_hours >= 0",
            name="ck_task_nodes_estimated_hours_non_negative",
        ),
        CheckConstraint(
            "actual_hours IS NULL OR actual_hours >= 0",
            name="ck_task_nodes_actual_hours_non_negative",
        ),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_task_nodes_progress_percent_range",
        ),
        Index(
            "ix_task_nodes_task_order",
            "task_id",
            "node_order",
            "sort_weight",
        ),
    )

    node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    node_order: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    node_name: Mapped[str] = mapped_column(String, nullable=False)
    action_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    tools_or_materials: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    planned_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    planned_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    actual_hours: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    deliverable: Mapped[str | None] = mapped_column(String, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(String, nullable=True)
    progress_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    task: Mapped[Task] = relationship(
        back_populates="nodes",
        foreign_keys=[task_id],
    )
    owner: Mapped[User | None] = relationship(
        back_populates="owned_task_nodes",
        foreign_keys=[owner_employee_no],
    )
    outgoing_dependencies: Mapped[list[TaskNodeDependency]] = relationship(
        back_populates="predecessor_node",
        primaryjoin=(
            "and_(TaskNode.task_id == TaskNodeDependency.task_id, "
            "TaskNode.node_id == foreign("
            "TaskNodeDependency.predecessor_node_id))"
        ),
        foreign_keys="TaskNodeDependency.predecessor_node_id",
    )
    incoming_dependencies: Mapped[list[TaskNodeDependency]] = relationship(
        back_populates="successor_node",
        primaryjoin=(
            "and_(TaskNode.task_id == TaskNodeDependency.task_id, "
            "TaskNode.node_id == foreign("
            "TaskNodeDependency.successor_node_id))"
        ),
        foreign_keys="TaskNodeDependency.successor_node_id",
    )
    participants: Mapped[list[TaskNodeParticipant]] = relationship(
        back_populates="node",
        primaryjoin=(
            "and_(TaskNode.task_id == foreign(TaskNodeParticipant.task_id), "
            "TaskNode.node_id == foreign(TaskNodeParticipant.node_id))"
        ),
        foreign_keys=(
            "[TaskNodeParticipant.task_id, TaskNodeParticipant.node_id]"
        ),
    )
