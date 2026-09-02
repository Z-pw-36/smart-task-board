"""Synchronous SQLAlchemy repositories for Phase 3 data access."""

from app.repositories.ai_extraction_record import AIExtractionRecordRepository
from app.repositories.department import DepartmentRepository
from app.repositories.operation_log import OperationLogRepository
from app.repositories.progress_report import ProgressReportRepository
from app.repositories.task import TaskRepository
from app.repositories.task_change_request import TaskChangeRequestRepository
from app.repositories.task_completion_review import (
    TaskCompletionReviewRepository,
)
from app.repositories.task_input import TaskInputRepository
from app.repositories.task_issue import TaskIssueRepository
from app.repositories.task_node import TaskNodeRepository
from app.repositories.task_performance_match import TaskPerformanceMatchRepository
from app.repositories.task_status_log import TaskStatusLogRepository
from app.repositories.user import UserRepository

__all__ = [
    "AIExtractionRecordRepository",
    "DepartmentRepository",
    "OperationLogRepository",
    "ProgressReportRepository",
    "TaskInputRepository",
    "TaskCompletionReviewRepository",
    "TaskIssueRepository",
    "TaskNodeRepository",
    "TaskPerformanceMatchRepository",
    "TaskRepository",
    "TaskChangeRequestRepository",
    "TaskStatusLogRepository",
    "UserRepository",
]
