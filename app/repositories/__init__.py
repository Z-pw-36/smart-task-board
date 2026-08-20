"""Synchronous SQLAlchemy repositories for Phase 3 data access."""

from app.repositories.ai_extraction_record import AIExtractionRecordRepository
from app.repositories.department import DepartmentRepository
from app.repositories.progress_report import ProgressReportRepository
from app.repositories.task import TaskRepository
from app.repositories.task_input import TaskInputRepository
from app.repositories.task_issue import TaskIssueRepository
from app.repositories.task_node import TaskNodeRepository
from app.repositories.task_status_log import TaskStatusLogRepository
from app.repositories.user import UserRepository

__all__ = [
    "AIExtractionRecordRepository",
    "DepartmentRepository",
    "ProgressReportRepository",
    "TaskInputRepository",
    "TaskIssueRepository",
    "TaskNodeRepository",
    "TaskRepository",
    "TaskStatusLogRepository",
    "UserRepository",
]
