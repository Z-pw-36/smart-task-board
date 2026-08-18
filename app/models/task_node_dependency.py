from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.task_node import TaskNode


class TaskNodeDependency(Base):
    """Directed dependency between two nodes in the same task."""

    __tablename__ = "task_node_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "predecessor_node_id"],
            ["task_nodes.task_id", "task_nodes.node_id"],
            ondelete="RESTRICT",
            name="fk_task_node_dependencies_predecessor_same_task",
        ),
        ForeignKeyConstraint(
            ["task_id", "successor_node_id"],
            ["task_nodes.task_id", "task_nodes.node_id"],
            ondelete="RESTRICT",
            name="fk_task_node_dependencies_successor_same_task",
        ),
        UniqueConstraint(
            "predecessor_node_id",
            "successor_node_id",
            "dependency_type",
            name="uq_task_node_dependencies_edge_type",
        ),
        CheckConstraint(
            "predecessor_node_id <> successor_node_id",
            name="ck_task_node_dependencies_not_self",
        ),
    )

    dependency_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    predecessor_node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    successor_node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    dependency_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="finish_to_start",
    )

    task: Mapped[Task] = relationship(
        back_populates="node_dependencies",
        foreign_keys=[task_id],
    )
    predecessor_node: Mapped[TaskNode] = relationship(
        back_populates="outgoing_dependencies",
        primaryjoin=(
            "and_(TaskNode.task_id == TaskNodeDependency.task_id, "
            "TaskNode.node_id == foreign("
            "TaskNodeDependency.predecessor_node_id))"
        ),
        foreign_keys=[predecessor_node_id],
    )
    successor_node: Mapped[TaskNode] = relationship(
        back_populates="incoming_dependencies",
        primaryjoin=(
            "and_(TaskNode.task_id == TaskNodeDependency.task_id, "
            "TaskNode.node_id == foreign("
            "TaskNodeDependency.successor_node_id))"
        ),
        foreign_keys=[successor_node_id],
    )
