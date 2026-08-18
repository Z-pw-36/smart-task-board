from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ai_extraction_record import AIExtractionRecord
    from app.models.user import User


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TaskInput(Base):
    """Original task description submitted by an employee."""

    __tablename__ = "task_inputs"

    input_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    input_type: Mapped[str] = mapped_column(String, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(String, nullable=True)
    voice_file_url: Mapped[str | None] = mapped_column(String, nullable=True)
    asr_text: Mapped[str | None] = mapped_column(String, nullable=True)
    source_channel: Mapped[str] = mapped_column(String, nullable=False)
    submitted_by_employee_no: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.employee_no", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        index=True,
    )

    submitted_by: Mapped[User] = relationship(
        back_populates="submitted_task_inputs",
        foreign_keys=[submitted_by_employee_no],
    )
    ai_extraction_records: Mapped[list[AIExtractionRecord]] = relationship(
        back_populates="input",
        foreign_keys="AIExtractionRecord.input_id",
    )
