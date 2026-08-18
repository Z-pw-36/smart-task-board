from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    get_current_employee_no,
    get_task_node_workflow_service,
    get_task_query_service,
    get_task_workflow_service,
)
from app.schemas import (
    CreateTaskRequest,
    ErrorResponse,
    NodeActionResponse,
    PaginatedTaskStatusLogResponse,
    ReturnTaskRequest,
    TaskActionRequest,
    TaskActionResponse,
    TaskDetailResponse,
    TaskNodeResponse,
    UpdateNodeProgressRequest,
)
from app.services.commands import (
    CreateTaskDraftCommand,
    TaskNodeDependencyDraft,
    TaskNodeDraft,
    TaskNodeParticipantDraft,
    TaskParticipantDraft,
)
from app.services.task_node_workflow import TaskNodeWorkflowService
from app.services.task_query import TaskQueryService
from app.services.task_workflow import TaskWorkflowService

router = APIRouter(prefix="/tasks", tags=["tasks"])
OPERATION_SOURCE = "rest_api"

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Identity header is missing"},
    403: {"model": ErrorResponse, "description": "Permission denied"},
    404: {"model": ErrorResponse, "description": "Entity not found"},
    409: {"model": ErrorResponse, "description": "State, version, or resource conflict"},
    422: {"model": ErrorResponse, "description": "Request or business validation failed"},
    500: {"model": ErrorResponse, "description": "Internal server error"},
}

Actor = Annotated[str, Depends(get_current_employee_no)]
TaskService = Annotated[TaskWorkflowService, Depends(get_task_workflow_service)]
NodeService = Annotated[TaskNodeWorkflowService, Depends(get_task_node_workflow_service)]
QueryService = Annotated[TaskQueryService, Depends(get_task_query_service)]


def _create_command(request: CreateTaskRequest, actor: str) -> CreateTaskDraftCommand:
    scalar_values = request.model_dump(
        exclude={
            "participants",
            "nodes",
            "dependencies",
            "node_participants",
            "extraction_record_ids",
        }
    )
    return CreateTaskDraftCommand(
        **scalar_values,
        creator_employee_no=actor,
        operation_source=OPERATION_SOURCE,
        participants=tuple(
            TaskParticipantDraft(**item.model_dump()) for item in request.participants
        ),
        nodes=tuple(TaskNodeDraft(**item.model_dump()) for item in request.nodes),
        dependencies=tuple(
            TaskNodeDependencyDraft(**item.model_dump()) for item in request.dependencies
        ),
        node_participants=tuple(
            TaskNodeParticipantDraft(**item.model_dump())
            for item in request.node_participants
        ),
        extraction_record_ids=request.extraction_record_ids,
    )


@router.post(
    "",
    response_model=TaskActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task draft",
    responses=ERROR_RESPONSES,
)
def create_task(
    request: CreateTaskRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    task = service.create_task_draft(_create_command(request, actor))
    return TaskActionResponse.model_validate(task)


@router.get(
    "/{task_id}",
    response_model=TaskDetailResponse,
    summary="Get task detail",
    responses=ERROR_RESPONSES,
)
def get_task_detail(
    task_id: UUID,
    actor: Actor,
    query_service: QueryService,
) -> dict[str, Any]:
    return query_service.get_task_detail(task_id, actor)


@router.get(
    "/{task_id}/nodes",
    response_model=list[TaskNodeResponse],
    summary="List task nodes",
    responses=ERROR_RESPONSES,
)
def list_task_nodes(
    task_id: UUID,
    actor: Actor,
    query_service: QueryService,
) -> list[dict[str, Any]]:
    return query_service.list_nodes(task_id, actor)


@router.get(
    "/{task_id}/nodes/{node_id}",
    response_model=TaskNodeResponse,
    summary="Get one task node",
    responses=ERROR_RESPONSES,
)
def get_task_node(
    task_id: UUID,
    node_id: UUID,
    actor: Actor,
    query_service: QueryService,
) -> dict[str, Any]:
    return query_service.get_node(task_id, node_id, actor)


@router.get(
    "/{task_id}/status-logs",
    response_model=PaginatedTaskStatusLogResponse,
    summary="List task status logs",
    responses=ERROR_RESPONSES,
)
def list_task_status_logs(
    task_id: UUID,
    actor: Actor,
    query_service: QueryService,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return query_service.list_status_logs(
        task_id,
        actor,
        limit=limit,
        offset=offset,
    )


def _task_response(task: Any) -> TaskActionResponse:
    return TaskActionResponse.model_validate(task)


@router.post(
    "/{task_id}/actions/submit-for-confirmation",
    response_model=TaskActionResponse,
    summary="Submit a draft for creator confirmation",
    responses=ERROR_RESPONSES,
)
def submit_for_confirmation(
    task_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.submit_for_confirmation(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
        )
    )


@router.post(
    "/{task_id}/actions/confirm-and-send",
    response_model=TaskActionResponse,
    summary="Confirm and send a task",
    responses=ERROR_RESPONSES,
)
def confirm_and_send(
    task_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.confirm_and_send(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
        )
    )


@router.post(
    "/{task_id}/actions/confirm-self-assigned",
    response_model=TaskActionResponse,
    summary="Confirm a self-assigned task",
    responses=ERROR_RESPONSES,
)
def confirm_self_assigned(
    task_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.confirm_self_assigned(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
        )
    )


@router.post(
    "/{task_id}/actions/accept",
    response_model=TaskActionResponse,
    summary="Accept a task",
    responses=ERROR_RESPONSES,
)
def accept_task(
    task_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.accept_task(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
        )
    )


@router.post(
    "/{task_id}/actions/return",
    response_model=TaskActionResponse,
    summary="Return a task to its creator",
    responses=ERROR_RESPONSES,
)
def return_task(
    task_id: UUID,
    request: ReturnTaskRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.return_task(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.reason,
        )
    )


@router.post(
    "/{task_id}/actions/resend",
    response_model=TaskActionResponse,
    summary="Resend a returned task",
    responses=ERROR_RESPONSES,
)
def resend_task(
    task_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.resend_task(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
        )
    )


@router.post(
    "/{task_id}/actions/submit-completion",
    response_model=TaskActionResponse,
    summary="Submit a completed task for review",
    responses=ERROR_RESPONSES,
)
def submit_completion(
    task_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.submit_completion(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
        )
    )


@router.post(
    "/{task_id}/actions/approve-completion",
    response_model=TaskActionResponse,
    summary="Approve task completion",
    responses=ERROR_RESPONSES,
)
def approve_completion(
    task_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.approve_completion(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
        )
    )


def _node_response(
    task_id: UUID,
    node_id: UUID,
    actor: str,
    query_service: TaskQueryService,
) -> NodeActionResponse:
    return NodeActionResponse.model_validate(
        query_service.get_node_action_snapshot(task_id, node_id, actor)
    )


@router.post(
    "/{task_id}/nodes/{node_id}/actions/start",
    response_model=NodeActionResponse,
    summary="Start a task node",
    responses=ERROR_RESPONSES,
)
def start_node(
    task_id: UUID,
    node_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: NodeService,
    query_service: QueryService,
) -> NodeActionResponse:
    service.start_node(
        task_id,
        node_id,
        actor,
        request.expected_task_version,
        OPERATION_SOURCE,
    )
    return _node_response(task_id, node_id, actor, query_service)


@router.patch(
    "/{task_id}/nodes/{node_id}/progress",
    response_model=NodeActionResponse,
    summary="Update task node progress",
    responses=ERROR_RESPONSES,
)
def update_node_progress(
    task_id: UUID,
    node_id: UUID,
    request: UpdateNodeProgressRequest,
    actor: Actor,
    service: NodeService,
    query_service: QueryService,
) -> NodeActionResponse:
    service.update_node_progress(
        task_id,
        node_id,
        actor,
        request.expected_task_version,
        OPERATION_SOURCE,
        request.progress_percent,
        request.actual_hours,
    )
    return _node_response(task_id, node_id, actor, query_service)


@router.post(
    "/{task_id}/nodes/{node_id}/actions/complete",
    response_model=NodeActionResponse,
    summary="Complete a task node",
    responses=ERROR_RESPONSES,
)
def complete_node(
    task_id: UUID,
    node_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: NodeService,
    query_service: QueryService,
) -> NodeActionResponse:
    service.complete_node(
        task_id,
        node_id,
        actor,
        request.expected_task_version,
        OPERATION_SOURCE,
    )
    return _node_response(task_id, node_id, actor, query_service)
