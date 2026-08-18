from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AIExtractionRecord


class AIExtractionRecordRepository:
    """Persistence and stable queries for AI extraction attempts."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, record: AIExtractionRecord) -> AIExtractionRecord:
        self.session.add(record)
        self.session.flush()
        return record

    def get_by_id(self, extraction_record_id: UUID) -> AIExtractionRecord | None:
        statement = select(AIExtractionRecord).where(
            AIExtractionRecord.extraction_id == extraction_record_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_input_id(self, input_id: UUID) -> list[AIExtractionRecord]:
        statement = (
            select(AIExtractionRecord)
            .where(AIExtractionRecord.input_id == input_id)
            .order_by(AIExtractionRecord.extraction_id)
        )
        return list(self.session.execute(statement).scalars().all())

    def list_by_task_id(self, task_id: UUID) -> list[AIExtractionRecord]:
        statement = (
            select(AIExtractionRecord)
            .where(AIExtractionRecord.task_id == task_id)
            .order_by(AIExtractionRecord.extraction_id)
        )
        return list(self.session.execute(statement).scalars().all())
