from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TaskProgressReport


class ProgressReportRepository:
    """Append-only persistence and timeline queries for progress reports."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, report: TaskProgressReport) -> TaskProgressReport:
        self.session.add(report)
        self.session.flush()
        return report

    def get_by_id(self, progress_report_id: UUID) -> TaskProgressReport | None:
        statement = select(TaskProgressReport).where(
            TaskProgressReport.progress_report_id == progress_report_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_task_and_id(
        self,
        task_id: UUID,
        progress_report_id: UUID,
    ) -> TaskProgressReport | None:
        statement = select(TaskProgressReport).where(
            TaskProgressReport.task_id == task_id,
            TaskProgressReport.progress_report_id == progress_report_id,
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_task_id(
        self,
        task_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[TaskProgressReport]:
        statement = (
            select(TaskProgressReport)
            .where(TaskProgressReport.task_id == task_id)
            .order_by(
                TaskProgressReport.created_at.desc(),
                TaskProgressReport.progress_report_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(statement).scalars().all())

    def count_by_task_id(self, task_id: UUID) -> int:
        statement = select(func.count()).select_from(TaskProgressReport).where(
            TaskProgressReport.task_id == task_id
        )
        return self.session.execute(statement).scalar_one()

    def has_root_task_report_for_period(
        self,
        task_id: UUID,
        report_period_end: datetime,
    ) -> bool:
        statement = select(
            select(TaskProgressReport.progress_report_id)
            .where(
                TaskProgressReport.task_id == task_id,
                TaskProgressReport.node_id.is_(None),
                TaskProgressReport.corrects_report_id.is_(None),
                TaskProgressReport.report_period_end == report_period_end,
            )
            .exists()
        )
        return bool(self.session.execute(statement).scalar_one())
