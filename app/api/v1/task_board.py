from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_employee_no, get_task_board_query_service
from app.schemas.common import TaskStatus
from app.schemas.task_board import (
    AvailableActionsResponse,
    DashboardSummaryResponse,
    InboxActionCode,
    PaginatedInboxResponse,
    PaginatedTaskBoardResponse,
)
from app.services.task_board_query import TaskBoardQueryService

router = APIRouter(tags=["task-board"])
Actor = Annotated[str, Depends(get_current_employee_no)]
BoardService = Annotated[TaskBoardQueryService, Depends(get_task_board_query_service)]
Relation = Literal["all", "created", "assigned", "participating"]


@router.get("/tasks", response_model=PaginatedTaskBoardResponse, summary="List my tasks")
def list_my_tasks(
    actor: Actor,
    service: BoardService,
    relation: Relation = "all",
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    return service.list_tasks(
        actor,
        relation=relation,
        task_status=task_status,
        search=search,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        limit=limit,
        offset=offset,
    )


@router.get("/tasks/inbox", response_model=PaginatedInboxResponse, summary="List my inbox")
def list_inbox(
    actor: Actor,
    service: BoardService,
    action_code: InboxActionCode | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, object]:
    return service.list_inbox(
        actor,
        action_code=action_code,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/tasks/{task_id}/available-actions",
    response_model=AvailableActionsResponse,
    summary="Get server-authorized task and node actions",
)
def get_available_actions(
    task_id: UUID,
    actor: Actor,
    service: BoardService,
) -> dict[str, object]:
    return service.available_actions(task_id, actor)


@router.get(
    "/dashboard/summary",
    response_model=DashboardSummaryResponse,
    summary="Get my real-time dashboard summary",
)
def get_dashboard_summary(
    actor: Actor,
    service: BoardService,
) -> dict[str, object]:
    return service.dashboard_summary(actor)
