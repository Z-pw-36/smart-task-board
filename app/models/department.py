from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class Department(Base):
    """Organizational department used for hierarchy and user scope."""

    __tablename__ = "departments"

    department_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    parent_department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.department_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    department_name: Mapped[str] = mapped_column(String, nullable=False)
    department_type: Mapped[str] = mapped_column(String, nullable=False)
    department_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)

    parent: Mapped[Department | None] = relationship(
        back_populates="children",
        remote_side=[department_id],
        foreign_keys=[parent_department_id],
    )
    children: Mapped[list[Department]] = relationship(
        back_populates="parent",
        foreign_keys=[parent_department_id],
    )
    users: Mapped[list[User]] = relationship(
        back_populates="department",
        foreign_keys="User.department_id",
    )
    tasks: Mapped[list[Task]] = relationship(
        back_populates="department",
        foreign_keys="Task.department_id",
    )
