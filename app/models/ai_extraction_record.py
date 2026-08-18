from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.task_input import TaskInput


class AIExtractionRecord(Base):
    """AI-proposed structure derived from one original task input."""

    __tablename__ = "ai_extraction_records"

    extraction_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    input_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("task_inputs.input_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    extracted_json: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    missing_fields: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    low_confidence_fields: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    confirm_questions: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    input: Mapped[TaskInput] = relationship(
        back_populates="ai_extraction_records",
        foreign_keys=[input_id],
    )
    task: Mapped[Task | None] = relationship(
        back_populates="ai_extraction_records",
        foreign_keys=[task_id],
    )
