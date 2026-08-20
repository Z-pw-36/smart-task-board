from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

from sqlalchemy.orm import Session

from app.repositories import (
    AIExtractionRecordRepository,
    DepartmentRepository,
    ProgressReportRepository,
    TaskCompletionReviewRepository,
    TaskInputRepository,
    TaskIssueRepository,
    TaskNodeRepository,
    TaskRepository,
    TaskStatusLogRepository,
    UserRepository,
)

SessionFactory = Callable[[], Session]


class UnitOfWork:
    """Own one synchronous Session and provide an explicit transaction boundary."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None
        self._committed = False
        self._rolled_back = False

    def __enter__(self) -> UnitOfWork:
        if self.session is not None:
            raise RuntimeError("UnitOfWork is already active")
        self.session = self._session_factory()
        self._committed = False
        self._rolled_back = False
        self.departments = DepartmentRepository(self.session)
        self.users = UserRepository(self.session)
        self.task_inputs = TaskInputRepository(self.session)
        self.ai_extraction_records = AIExtractionRecordRepository(self.session)
        self.tasks = TaskRepository(self.session)
        self.task_completion_reviews = TaskCompletionReviewRepository(
            self.session
        )
        self.task_nodes = TaskNodeRepository(self.session)
        self.progress_reports = ProgressReportRepository(self.session)
        self.task_issues = TaskIssueRepository(self.session)
        self.task_status_logs = TaskStatusLogRepository(self.session)
        return self

    def commit(self) -> None:
        session = self._require_session()
        try:
            session.commit()
        except Exception:
            session.rollback()
            self._rolled_back = True
            raise
        self._committed = True

    def rollback(self) -> None:
        session = self._require_session()
        session.rollback()
        self._rolled_back = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        session = self._require_session()
        try:
            if exc_type is not None and not self._rolled_back:
                session.rollback()
                self._rolled_back = True
            elif not self._committed and not self._rolled_back:
                session.rollback()
                self._rolled_back = True
        finally:
            session.close()
            self.session = None
        return False

    def _require_session(self) -> Session:
        if self.session is None:
            raise RuntimeError("UnitOfWork is not active")
        return self.session
