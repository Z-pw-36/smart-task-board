from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.models import TaskIssue
from app.services.progress_issue_query import ProgressIssueQueryService
from app.services.task_issue import issue_allowed_actions

NOW = datetime(2026, 8, 19, 2, 0, tzinfo=UTC)


def _service() -> ProgressIssueQueryService:
    service = ProgressIssueQueryService(MagicMock(), clock=lambda: NOW)
    service._tasks = MagicMock()
    service._reports = MagicMock()
    service._issues = MagicMock()
    return service


def test_report_due_is_read_only_and_excludes_fulfilled_periods() -> None:
    service = _service()
    due = SimpleNamespace(
        task_id=uuid4(),
        task_no="TASK-1",
        task_name="Due",
        task_version=5,
        report_cycle="weekly:WED@09:00",
        accepted_at=datetime(2026, 8, 17, 1, 0, tzinfo=UTC),
        deadline=None,
    )
    fulfilled = SimpleNamespace(
        task_id=uuid4(),
        task_no="TASK-2",
        task_name="Done",
        task_version=3,
        report_cycle="weekly:WED@09:00",
        accepted_at=datetime(2026, 8, 17, 1, 0, tzinfo=UTC),
        deadline=None,
    )
    service._tasks.list_report_due_candidates.return_value = [due, fulfilled]
    service._reports.has_root_task_report_for_period.side_effect = (
        lambda task_id, _end: task_id == fulfilled.task_id
    )

    result = service.list_report_due("ASSIGNEE")

    assert result["total"] == 1
    assert result["items"][0]["task_id"] == due.task_id
    assert result["items"][0]["report_period_end"] == datetime(
        2026, 8, 19, 1, 0, tzinfo=UTC
    )
    assert result["items"][0]["overdue_seconds"] == 3600


def test_issue_allowed_actions_follow_owner_reporter_separation() -> None:
    issue = TaskIssue(
        issue_id=uuid4(),
        task_id=uuid4(),
        reported_by_employee_no="REPORTER",
        issue_type="blocker",
        title="Blocked",
        description="Blocked",
        severity="high",
        status="open",
        owner_employee_no="OWNER",
        created_at=NOW,
    )

    assert issue_allowed_actions(issue, "OWNER") == [
        "start_processing",
        "resolve",
        "reject",
    ]
    assert issue_allowed_actions(issue, "REPORTER") == []
    issue.status = "resolved"
    assert issue_allowed_actions(issue, "REPORTER") == ["close"]
    assert issue_allowed_actions(issue, "OWNER") == []
