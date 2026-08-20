from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.models import Task, TaskCompletionReview, TaskNode, TaskNodeDependency
from app.services.task_board_query import (
    TaskBoardQueryService,
    _node_actions,
    _task_actions,
)

NOW = datetime(2026, 8, 18, 8, 0, tzinfo=UTC)


def _task(status: str, **overrides: object) -> Task:
    values: dict[str, object] = {
        "task_id": uuid4(),
        "task_name": "Board task",
        "creator_employee_no": "E-CREATOR",
        "main_assignee_employee_no": "E-ASSIGNEE",
        "reviewer_employee_no": "E-REVIEWER",
        "status": status,
        "task_version": 3,
        "created_at": NOW - timedelta(days=1),
        "updated_at": NOW,
    }
    values.update(overrides)
    return Task(**values)


def _node(task: Task, status: str = "pending", **overrides: object) -> TaskNode:
    values: dict[str, object] = {
        "node_id": uuid4(),
        "task_id": task.task_id,
        "node_order": 1,
        "node_name": "Do work",
        "owner_employee_no": "E-OWNER",
        "status": status,
        "progress_percent": 0,
    }
    values.update(overrides)
    return TaskNode(**values)


def _review(task: Task, status: str = "submitted", **overrides: object) -> TaskCompletionReview:
    values: dict[str, object] = {
        "completion_review_id": uuid4(),
        "task_id": task.task_id,
        "review_round": 1,
        "submitted_by_employee_no": "E-ASSIGNEE",
        "completion_note": "Done",
        "deliverable_summary": "Delivered",
        "reviewer_employee_no": "E-REVIEWER",
        "review_status": status,
        "submitted_task_version": 3,
        "submitted_at": NOW,
        "is_legacy_import": False,
    }
    values.update(overrides)
    return TaskCompletionReview(**values)


def test_task_actions_match_phase4_state_and_actor_rules() -> None:
    node = _node(_task("draft"))
    draft = _task("draft")
    assert _task_actions(draft, "E-CREATOR", [node]) == ["submit_for_confirmation"]
    assert _task_actions(draft, "E-OUTSIDE", [node]) == []
    pending = _task("pending_confirmation")
    assert _task_actions(pending, "E-CREATOR", [node]) == ["confirm_and_send"]
    self_assigned = _task("pending_confirmation", main_assignee_employee_no="E-CREATOR")
    assert _task_actions(self_assigned, "E-CREATOR", [node]) == ["confirm_self_assigned"]
    acceptance = _task("pending_acceptance")
    assert _task_actions(acceptance, "E-ASSIGNEE", [node]) == ["accept", "return"]
    assert _task_actions(_task("returned"), "E-CREATOR", [node]) == ["resend"]
    completed_node = _node(_task("in_progress"), status="completed", progress_percent=100)
    assert _task_actions(_task("in_progress"), "E-ASSIGNEE", [completed_node]) == [
        "submit_progress_report",
        "report_task_issue",
        "submit_completion",
    ]
    assert "submit_completion" not in _task_actions(
        _task("in_progress"),
        "E-ASSIGNEE",
        [completed_node],
        has_non_closed_issue=True,
    )
    pending_review = _task("pending_review")
    assert _task_actions(
        pending_review,
        "E-REVIEWER",
        [node],
        current_review=_review(pending_review),
    ) == [
        "approve_completion",
        "reject_completion",
    ]
    assert _task_actions(pending_review, "E-REVIEWER", [node]) == []
    in_progress = _task("in_progress")
    assert _task_actions(in_progress, "E-CREATOR", [node]) == ["report_task_issue"]
    assert _task_actions(
        in_progress,
        "E-PARTICIPANT",
        [node],
        is_task_participant=True,
    ) == ["report_task_issue"]


def test_targeted_rework_requires_explicit_reopen_before_resubmission() -> None:
    task = _task("in_progress")
    node = _node(task, status="completed", progress_percent=100)
    rejected = _review(
        task,
        status="rejected",
        review_result="rejected",
        reject_reason="Revise the selected node",
        rework_node_id=node.node_id,
        reviewed_task_version=4,
        reviewed_at=NOW,
    )

    blocked = _task_actions(
        task,
        "E-ASSIGNEE",
        [node],
        latest_review=rejected,
        rework_node_reopened=False,
    )
    assert "submit_completion" not in blocked

    reopened = _task_actions(
        task,
        "E-ASSIGNEE",
        [node],
        latest_review=rejected,
        rework_node_reopened=True,
    )
    assert "submit_completion" in reopened


def test_node_actions_keep_owner_fallback_and_dependency_rules() -> None:
    task = _task("in_progress")
    predecessor = _node(task, status="pending", node_order=1)
    successor = _node(task, status="pending", node_order=2)
    dependency = TaskNodeDependency(
        dependency_id=uuid4(),
        task_id=task.task_id,
        predecessor_node_id=predecessor.node_id,
        successor_node_id=successor.node_id,
    )
    nodes = {predecessor.node_id: predecessor, successor.node_id: successor}
    arguments = {
        "can_execute": True,
        "can_report": True,
        "has_active_blocker": False,
    }
    assert _node_actions(task, successor, "E-OWNER", [dependency], nodes, **arguments) == [
        "submit_progress_report",
        "report_task_issue",
    ]
    predecessor.status = "completed"
    assert _node_actions(task, successor, "E-OWNER", [dependency], nodes, **arguments) == [
        "start_node",
        "submit_progress_report",
        "report_task_issue",
    ]
    successor.status = "in_progress"
    assert _node_actions(task, successor, "E-OWNER", [dependency], nodes, **arguments) == [
        "update_node_progress",
        "submit_progress_report",
        "report_task_issue",
        "complete_node",
    ]
    assert (
        _node_actions(
            task,
            successor,
            "E-NODE-PARTICIPANT",
            [],
            nodes,
            can_execute=False,
            can_report=False,
            has_active_blocker=False,
        )
        == []
    )
    assert _node_actions(
        task,
        successor,
        "E-NODE-PARTICIPANT",
        [],
        nodes,
        can_execute=False,
        can_report=True,
        has_active_blocker=False,
    ) == ["submit_progress_report", "report_task_issue"]
    successor.owner_employee_no = None
    assert _node_actions(task, successor, "E-ASSIGNEE", [], nodes, **arguments) == [
        "update_node_progress",
        "submit_progress_report",
        "report_task_issue",
        "complete_node",
    ]
    assert "complete_node" not in _node_actions(
        task,
        successor,
        "E-ASSIGNEE",
        [],
        nodes,
        can_execute=True,
        can_report=True,
        has_active_blocker=True,
    )
    successor.status = "completed"
    assert _node_actions(
        task,
        successor,
        "E-REVIEWER",
        [],
        nodes,
        can_execute=False,
        can_report=False,
        has_active_blocker=False,
        can_reopen=True,
    ) == ["reopen_node"]


def test_inbox_projects_task_and_node_actions_with_expected_version() -> None:
    service = TaskBoardQueryService(MagicMock(), clock=lambda: NOW)
    task = _task("in_progress", deadline=NOW - timedelta(hours=1))
    node = _node(task, status="in_progress")
    service._tasks = MagicMock()
    service._nodes = MagicMock()
    service._users = MagicMock()
    service._issues = MagicMock()
    service._reports = MagicMock()
    service._completion_reviews = MagicMock()
    service._logs = MagicMock()
    service._completion_reviews.list_submitted_for_reviewer.return_value = []
    service._completion_reviews.list_rejected_rework_candidates_for_reviewer.return_value = []
    service._completion_reviews.get_current_submitted.return_value = None
    service._completion_reviews.get_latest.return_value = None
    service._issues.has_non_closed.return_value = False
    service._issues.has_active_blocker.return_value = False
    service._tasks.list_inbox_candidates.return_value = [task]
    service._tasks.list_participants.return_value = []
    service._nodes.list_nodes.return_value = [node]
    service._nodes.list_dependencies.return_value = []
    service._nodes.list_participants_by_task_id.return_value = [
        SimpleNamespace(employee_no="E-NODE-PARTICIPANT")
    ]
    service._users.list_by_employee_nos.return_value = [
        SimpleNamespace(employee_no="E-CREATOR", name="Creator"),
        SimpleNamespace(employee_no="E-ASSIGNEE", name="Assignee"),
    ]
    result = service.list_inbox("E-OWNER", action_code=None, limit=20, offset=0)
    assert result["total"] == 2
    assert {item["action_code"] for item in result["items"]} == {
        "update_node",
        "complete_node",
    }
    assert all(item["expected_task_version"] == 3 for item in result["items"])
    assert all(item["is_overdue"] is True for item in result["items"])


def test_inbox_projects_issue_owner_actions_and_issue_relation() -> None:
    service = TaskBoardQueryService(MagicMock(), clock=lambda: NOW)
    task = _task("in_progress")
    node = _node(task, status="in_progress")
    issue = SimpleNamespace(
        issue_id=uuid4(),
        task_id=task.task_id,
        node_id=node.node_id,
        status="open",
        owner_employee_no="E-ISSUE-OWNER",
        reported_by_employee_no="E-ASSIGNEE",
        severity="high",
        issue_type="blocker",
        title="Waiting for access",
        created_at=NOW,
    )
    service._tasks = MagicMock()
    service._nodes = MagicMock()
    service._users = MagicMock()
    service._issues = MagicMock()
    service._reports = MagicMock()
    service._completion_reviews = MagicMock()
    service._logs = MagicMock()
    service._completion_reviews.list_submitted_for_reviewer.return_value = []
    service._completion_reviews.list_rejected_rework_candidates_for_reviewer.return_value = []
    service._completion_reviews.get_current_submitted.return_value = None
    service._completion_reviews.get_latest.return_value = None
    service._tasks.list_inbox_candidates.return_value = []
    service._tasks.get_by_id.return_value = task
    service._tasks.list_participants.return_value = []
    service._nodes.list_nodes.return_value = [node]
    service._nodes.list_dependencies.return_value = []
    service._nodes.list_participants_by_task_id.return_value = []
    service._users.list_by_employee_nos.return_value = []
    service._issues.list_actionable_for.return_value = [issue]
    service._issues.has_non_closed.return_value = True
    service._issues.has_employee_relation.return_value = True

    result = service.list_inbox(
        "E-ISSUE-OWNER",
        action_code="handle_issue",
        limit=20,
        offset=0,
    )

    assert result["total"] == 1
    item = result["items"][0]
    assert item["allowed_actions"] == [
        "start_processing_issue",
        "resolve_issue",
        "reject_issue",
    ]
    assert item["node"]["node_id"] == node.node_id
    assert item["endpoint"].endswith(f"/{issue.issue_id}/actions")
    assert "issue_participant" in item["task"]["current_user_relations"]


def test_dashboard_uses_bounded_real_time_counts_and_seven_day_window() -> None:
    service = TaskBoardQueryService(MagicMock(), clock=lambda: NOW)
    service._tasks = MagicMock()
    service._nodes = MagicMock()
    service._users = MagicMock()
    service._issues = MagicMock()
    service._reports = MagicMock()
    service._completion_reviews = MagicMock()
    service._logs = MagicMock()
    service._completion_reviews.list_submitted_for_reviewer.return_value = []
    service._completion_reviews.list_rejected_rework_candidates_for_reviewer.return_value = []
    service._issues.count_open_owned_by.return_value = 6
    service._tasks.list_recent_related.return_value = []
    service._tasks.list_inbox_candidates.return_value = []
    service._tasks.count_related.side_effect = [2, 3, 4, 5, 1]
    result = service.dashboard_summary("E-CREATOR")
    assert result == {
        "created_task_count": 2,
        "assigned_task_count": 3,
        "inbox_count": 0,
        "in_progress_count": 4,
        "due_within_7_days_count": 5,
        "overdue_count": 1,
        "report_due_count": 0,
        "open_issue_count": 6,
        "due_window_days": 7,
        "recent_tasks": [],
    }
