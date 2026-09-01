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
    SortOrder,
    TaskOverviewDatePreset,
    TaskOverviewMode,
    TaskOverviewQuadrant,
    TaskOverviewSort,
    TaskOverviewSupport,
)
from app.services.errors import BusinessValidationError
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
    mode: TaskOverviewMode = "tasks",
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    quadrant: TaskOverviewQuadrant | None = None,
    support: TaskOverviewSupport | None = None,
    near_due: Annotated[bool, Query(alias="nearDue")] = False,
    date_preset: Annotated[TaskOverviewDatePreset, Query(alias="datePreset")] = "all",
    search: Annotated[str | None, Query(max_length=200)] = None,
    deadline_from: date | None = None,
    deadline_to: date | None = None,
    start_date: Annotated[date | None, Query(alias="startDate")] = None,
    end_date: Annotated[date | None, Query(alias="endDate")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int | None, Query(alias="pageSize", ge=1, le=100)] = None,
    sort_by: Annotated[TaskOverviewSort, Query(alias="sortBy")] = "deadline",
    sort_order: Annotated[SortOrder, Query(alias="sortOrder")] = "asc",
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int | None, Query(ge=0)] = None,
) -> dict[str, object]:
    effective_limit = page_size or limit or 20
    effective_offset = offset if offset is not None else (page - 1) * effective_limit
    effective_page = effective_offset // effective_limit + 1 if offset is not None else page
    if deadline_from and deadline_to and deadline_from > deadline_to:
        raise BusinessValidationError("deadline_from must not be after deadline_to")
    if start_date and end_date and start_date > end_date:
        raise BusinessValidationError("startDate must not be after endDate")
    return service.list_tasks(
        actor,
        relation=relation,
        mode=mode,
        task_status=task_status,
        quadrant=quadrant,
        support=support,
        near_due=near_due,
        date_preset=date_preset,
        search=search,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order,
        page=effective_page,
        page_size=effective_limit,
        limit=effective_limit,
        offset=effective_offset,
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
