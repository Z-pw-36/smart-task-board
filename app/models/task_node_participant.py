from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task_node import TaskNode
    from app.models.user import User


class TaskNodeParticipant(Base):
    """Employee collaboration role attached to one task node."""

    __tablename__ = "task_node_participants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "node_id"],
            ["task_nodes.task_id", "task_nodes.node_id"],
            ondelete="RESTRICT",
            name="fk_task_node_participants_node_same_task",
        ),
        UniqueConstraint(
            "task_id",
            "node_id",
            "employee_no",
            "participant_role",
            name="uq_task_node_participants_task_node_employee_role",
        ),
    )

    node_participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    node_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    participant_role: Mapped[str] = mapped_column(String, nullable=False)

    node: Mapped[TaskNode] = relationship(
        back_populates="participants",
        primaryjoin=(
            "and_(TaskNode.task_id == foreign(TaskNodeParticipant.task_id), "
            "TaskNode.node_id == foreign(TaskNodeParticipant.node_id))"
        ),
        foreign_keys=[task_id, node_id],
    )
    employee: Mapped[User] = relationship(
        back_populates="task_node_participations",
        foreign_keys=[employee_no],
    )
