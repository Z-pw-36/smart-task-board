from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import StrictSchema, TaskStatus

type TaskRelation = Literal["all", "created", "assigned", "participating"]
type TaskOverviewMode = Literal["tasks", "nodes"]
type TaskOverviewQuadrant = Literal[
    "important_urgent",
    "important_not_urgent",
    "urgent_not_important",
    "routine",
]
type TaskOverviewSort = Literal["deadline", "created_at", "updated_at", "status", "task_weight"]
type SortOrder = Literal["asc", "desc"]
type TaskOverviewDatePreset = Literal["all", "week", "month", "custom"]
type TaskOverviewSupport = Literal["open"]
type AllowedAction = Literal[
    "submit_for_confirmation",
    "confirm_and_send",
    "confirm_self_assigned",
    "accept",
    "return",
    "resend",
    "plan_task",
    "start_node",
    "update_node_progress",
    "complete_node",
    "submit_completion",
    "approve_completion",
    "reject_completion",
    "reopen_node",
    "submit_change_request",
    "approve_change_request",
    "reject_change_request",
    "cancel_change_request",
    "cancel_task",
    "withdraw_task",
    "merge_task",
    "close_task",
    "archive_task",
    "restore_task",
    "submit_progress_report",
    "report_task_issue",
    "start_processing_issue",
    "resolve_issue",
    "reject_issue",
    "close_issue",
]
type InboxActionCode = Literal[
    "confirm_task",
    "accept_task",
    "handle_returned_task",
    "plan_task",
    "start_node",
    "update_node",
    "complete_node",
    "submit_completion",
    "approve_completion",
    "reopen_node",
    "approve_change_request",
    "cancel_change_request",
    "withdraw_task",
    "report_due",
    "handle_issue",
    "submit_change_request",
    "approve_change_request",
    "reject_change_request",
    "cancel_change_request",
    "cancel_task",
    "withdraw_task",
    "merge_task",
    "close_task",
    "archive_task",
    "restore_task",
]


class EmployeeSummaryResponse(StrictSchema):
    employee_no: str
    name: str


class TaskBoardSummaryResponse(StrictSchema):
    task_id: UUID
    task_no: str | None
    task_name: str
    status: TaskStatus
    deadline: datetime | None
    is_urgent: bool | None
    task_weight: int | None
    task_version: int
    creator: EmployeeSummaryResponse
    main_assignee: EmployeeSummaryResponse | None
    current_user_relations: list[str]
    allowed_actions: list[AllowedAction]
    is_overdue: bool
    days_until_deadline: int | None
    created_at: datetime
    updated_at: datetime


class TaskOverviewNodeResponse(StrictSchema):
    node_id: UUID
    task_id: UUID
    task_no: str | None
    task_name: str
    node_name: str
    status: str
    task_status: TaskStatus
    owner: EmployeeSummaryResponse | None
    planned_start_time: datetime | None
    planned_deadline: datetime | None
    progress_percent: int
    current_user_relations: list[str]
    is_overdue: bool
    days_until_deadline: int | None
    created_at: datetime
    updated_at: datetime


class PaginatedTaskBoardResponse(StrictSchema):
    items: list[TaskBoardSummaryResponse | TaskOverviewNodeResponse]
    limit: int
    offset: int
    page: int = 1
    pageSize: int = 20
    total: int
    status_counts: dict[str, int] = Field(default_factory=dict)


class InboxNodeSummaryResponse(StrictSchema):
    node_id: UUID
    node_name: str
    status: str
    progress_percent: int
    owner_employee_no: str | None


class InboxItemResponse(StrictSchema):
    inbox_item_type: str
    action_code: InboxActionCode
    task: TaskBoardSummaryResponse
    node: InboxNodeSummaryResponse | None
    reason: str
    expected_task_version: int
    endpoint: str
    allowed_actions: list[AllowedAction]
    is_overdue: bool
    relevant_at: datetime


class PaginatedInboxResponse(StrictSchema):
    items: list[InboxItemResponse]
    limit: int
    offset: int
    total: int


class NodeAllowedActionsResponse(StrictSchema):
    node_id: UUID
    allowed_actions: list[AllowedAction]


class AvailableActionsResponse(StrictSchema):
    task_id: UUID
    task_version: int
    allowed_actions: list[AllowedAction]
    nodes: list[NodeAllowedActionsResponse]


class DashboardSummaryResponse(StrictSchema):
    created_task_count: int
    assigned_task_count: int
    inbox_count: int
    in_progress_count: int
    pending_acceptance_count: int = 0
    today_task_count: int = 0
    due_within_7_days_count: int
    overdue_count: int
    report_due_count: int
    open_issue_count: int
    blocked_task_count: int = 0
    completion_review_count: int = 0
    unread_notification_count: int = 0
    open_conflict_count: int = 0
    due_window_days: int = 7
    recent_tasks: list[TaskBoardSummaryResponse]
    latest_workload: dict[str, Any] | None = None
    priority_items: list[dict[str, Any]] = Field(default_factory=list)
