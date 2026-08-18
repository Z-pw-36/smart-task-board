from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.task import Task
    from app.models.task_input import TaskInput
    from app.models.task_node import TaskNode
    from app.models.task_node_participant import TaskNodeParticipant
    from app.models.task_participant import TaskParticipant
    from app.models.task_status_log import TaskStatusLog


class User(Base):
    """Employee identity synchronized from organizational data sources."""

    __tablename__ = "users"

    employee_no: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.department_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    position: Mapped[str | None] = mapped_column(String, nullable=True)
    manager_employee_no: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    org_level: Mapped[str | None] = mapped_column(String, nullable=True)
    wecom_user_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        unique=True,
    )
    role_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)

    department: Mapped[Department | None] = relationship(
        back_populates="users",
        foreign_keys=[department_id],
    )
    manager: Mapped[User | None] = relationship(
        back_populates="direct_reports",
        remote_side=[employee_no],
        foreign_keys=[manager_employee_no],
    )
    direct_reports: Mapped[list[User]] = relationship(
        back_populates="manager",
        foreign_keys=[manager_employee_no],
    )
    submitted_task_inputs: Mapped[list[TaskInput]] = relationship(
        back_populates="submitted_by",
        foreign_keys="TaskInput.submitted_by_employee_no",
    )
    created_tasks: Mapped[list[Task]] = relationship(
        back_populates="creator",
        foreign_keys="Task.creator_employee_no",
    )
    assigned_tasks: Mapped[list[Task]] = relationship(
        back_populates="main_assignee",
        foreign_keys="Task.main_assignee_employee_no",
    )
    reporting_tasks: Mapped[list[Task]] = relationship(
        back_populates="report_to",
        foreign_keys="Task.report_to_employee_no",
    )
    review_tasks: Mapped[list[Task]] = relationship(
        back_populates="reviewer",
        foreign_keys="Task.reviewer_employee_no",
    )
    task_participations: Mapped[list[TaskParticipant]] = relationship(
        back_populates="employee",
        foreign_keys="TaskParticipant.employee_no",
    )
    owned_task_nodes: Mapped[list[TaskNode]] = relationship(
        back_populates="owner",
        foreign_keys="TaskNode.owner_employee_no",
    )
    task_node_participations: Mapped[list[TaskNodeParticipant]] = relationship(
        back_populates="employee",
        foreign_keys="TaskNodeParticipant.employee_no",
    )
    operated_task_status_logs: Mapped[list[TaskStatusLog]] = relationship(
        back_populates="operator",
        foreign_keys="TaskStatusLog.operator_employee_no",
    )
    targeted_task_status_logs: Mapped[list[TaskStatusLog]] = relationship(
        back_populates="target_employee",
        foreign_keys="TaskStatusLog.target_employee_no",
    )
