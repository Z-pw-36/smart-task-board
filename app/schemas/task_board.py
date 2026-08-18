from datetime import datetime
from typing import Literal
from uuid import UUID

from app.schemas.common import StrictSchema, TaskStatus

type TaskRelation = Literal["all", "created", "assigned", "participating"]
type AllowedAction = Literal[
    "submit_for_confirmation",
    "confirm_and_send",
    "confirm_self_assigned",
    "accept",
    "return",
    "resend",
    "start_node",
    "update_node_progress",
    "complete_node",
    "submit_completion",
    "approve_completion",
]
type InboxActionCode = Literal[
    "confirm_task",
    "accept_task",
    "handle_returned_task",
    "start_node",
    "update_node",
    "complete_node",
    "submit_completion",
    "approve_completion",
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


class PaginatedTaskBoardResponse(StrictSchema):
    items: list[TaskBoardSummaryResponse]
    limit: int
    offset: int
    total: int


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
    due_within_7_days_count: int
    overdue_count: int
    due_window_days: int = 7
    recent_tasks: list[TaskBoardSummaryResponse]
