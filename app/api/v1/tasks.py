from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    get_current_employee_no,
    get_intake_service,
    get_task_node_workflow_service,
    get_task_query_service,
    get_task_workflow_service,
)
from app.schemas import (
    CancelTaskChangeRequest,
    CompletionDecisionRequest,
    CompletionReviewActionResponse,
    CompletionReviewResponse,
    ConfirmTaskPlanningRequest,
    CreateTaskRequest,
    ErrorResponse,
    MergeTaskRequest,
    NodeActionResponse,
    PaginatedCompletionReviewResponse,
    PaginatedTaskChangeRequestResponse,
    PaginatedTaskStatusLogResponse,
    ReasonTaskActionRequest,
    RejectCompletionRequest,
    ReopenNodeRequest,
    RestoreTaskRequest,
    ReturnTaskRequest,
    SubmitCompletionRequest,
    TaskActionRequest,
    TaskActionResponse,
    TaskChangeRequestActionResponse,
    TaskChangeRequestCreate,
    TaskChangeRequestDecisionRequest,
    TaskChangeRequestRejectRequest,
    TaskChangeRequestResponse,
    TaskDetailResponse,
    TaskNodeResponse,
    TaskPlanningSuggestionRequest,
    TaskPlanningSuggestionResponse,
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
IntakeService = Annotated[Any, Depends(get_intake_service)]


def _create_command(request: CreateTaskRequest, actor: str) -> CreateTaskDraftCommand:
    scalar_values = request.model_dump(
        exclude={
            "task_id",
            "participants",
            "nodes",
            "dependencies",
            "node_participants",
            "extraction_record_ids",
        }
    )
    command_values = {
        **scalar_values,
        "creator_employee_no": actor,
        "operation_source": OPERATION_SOURCE,
        "participants": tuple(
            TaskParticipantDraft(**item.model_dump()) for item in request.participants
        ),
        "nodes": tuple(TaskNodeDraft(**item.model_dump()) for item in request.nodes),
        "dependencies": tuple(
            TaskNodeDependencyDraft(**item.model_dump()) for item in request.dependencies
        ),
        "node_participants": tuple(
            TaskNodeParticipantDraft(**item.model_dump()) for item in request.node_participants
        ),
        "extraction_record_ids": request.extraction_record_ids,
    }
    if request.task_id is not None:
        command_values["task_id"] = request.task_id
    return CreateTaskDraftCommand(**command_values)


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


@router.post(
    "/{task_id}/planning/decompose",
    response_model=TaskPlanningSuggestionResponse,
    summary="Generate AI task planning suggestions for the accepted main assignee",
    responses=ERROR_RESPONSES,
)
def decompose_task_plan(
    task_id: UUID,
    request: TaskPlanningSuggestionRequest,
    actor: Actor,
    service: IntakeService,
) -> dict[str, object]:
    return service.suggest_task_plan(
        actor,
        task_id,
        instructions=request.instructions,
    )


@router.post(
    "/{task_id}/planning/confirm",
    response_model=TaskActionResponse,
    summary="Confirm an accepted task plan and persist executable nodes",
    responses=ERROR_RESPONSES,
)
def confirm_task_plan(
    task_id: UUID,
    request: ConfirmTaskPlanningRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    enabled_nodes = [
        TaskNodeDraft(**node.model_dump(exclude={"enabled"}))
        for node in request.nodes
        if node.enabled
    ]
    enabled_node_ids = {node.node_id for node in enabled_nodes}
    return _task_response(
        service.confirm_task_plan(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            tuple(enabled_nodes),
            tuple(
                TaskNodeDependencyDraft(**dependency.model_dump())
                for dependency in request.dependencies
                if dependency.predecessor_node_id in enabled_node_ids
                and dependency.successor_node_id in enabled_node_ids
            ),
            tuple(
                TaskNodeParticipantDraft(**participant.model_dump())
                for participant in request.node_participants
                if participant.node_id in enabled_node_ids
            ),
        )
    )


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


@router.get(
    "/{task_id}/completion-reviews",
    response_model=PaginatedCompletionReviewResponse,
    summary="List immutable completion review rounds",
    responses=ERROR_RESPONSES,
)
def list_completion_reviews(
    task_id: UUID,
    actor: Actor,
    query_service: QueryService,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return query_service.list_completion_reviews(
        task_id,
        actor,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{task_id}/completion-reviews/{completion_review_id}",
    response_model=CompletionReviewResponse,
    summary="Get one completion review round",
    responses=ERROR_RESPONSES,
)
def get_completion_review(
    task_id: UUID,
    completion_review_id: UUID,
    actor: Actor,
    query_service: QueryService,
) -> dict[str, Any]:
    return query_service.get_completion_review(
        task_id,
        completion_review_id,
        actor,
    )


def _task_response(task: Any) -> TaskActionResponse:
    return TaskActionResponse.model_validate(task)


def _completion_response(result: Any) -> CompletionReviewActionResponse:
    task, review = result
    return CompletionReviewActionResponse(
        task_id=task.task_id,
        status=task.status,
        task_version=task.task_version,
        updated_at=task.updated_at,
        review=CompletionReviewResponse.model_validate(review),
    )


def _change_request_response(result: Any) -> TaskChangeRequestActionResponse:
    task, request = result
    return TaskChangeRequestActionResponse(
        task_id=task.task_id,
        status=task.status,
        task_version=task.task_version,
        updated_at=task.updated_at,
        change_request=TaskChangeRequestResponse.model_validate(request),
    )


@router.post(
    "/{task_id}/change-requests",
    response_model=TaskChangeRequestActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an immutable task change request",
    responses=ERROR_RESPONSES,
)
def submit_change_request(
    task_id: UUID,
    request: TaskChangeRequestCreate,
    actor: Actor,
    service: TaskService,
) -> TaskChangeRequestActionResponse:
    return _change_request_response(
        service.submit_change_request(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.patch_json,
            request.reason,
        )
    )


@router.get(
    "/{task_id}/change-requests",
    response_model=PaginatedTaskChangeRequestResponse,
    summary="List immutable task change requests",
    responses=ERROR_RESPONSES,
)
def list_change_requests(
    task_id: UUID,
    actor: Actor,
    query_service: QueryService,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return query_service.list_change_requests(
        task_id,
        actor,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{task_id}/change-requests/{change_request_id}",
    response_model=TaskChangeRequestResponse,
    summary="Get one task change request",
    responses=ERROR_RESPONSES,
)
def get_change_request(
    task_id: UUID,
    change_request_id: UUID,
    actor: Actor,
    query_service: QueryService,
) -> dict[str, Any]:
    return query_service.get_change_request(task_id, change_request_id, actor)


@router.post(
    "/{task_id}/change-requests/{change_request_id}/actions/approve",
    response_model=TaskChangeRequestActionResponse,
    summary="Approve and atomically apply a task change request",
    responses=ERROR_RESPONSES,
)
def approve_change_request(
    task_id: UUID,
    change_request_id: UUID,
    request: TaskChangeRequestDecisionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskChangeRequestActionResponse:
    return _change_request_response(
        service.approve_change_request(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            change_request_id,
            request.approval_comment,
        )
    )


@router.post(
    "/{task_id}/change-requests/{change_request_id}/actions/reject",
    response_model=TaskChangeRequestActionResponse,
    summary="Reject a task change request",
    responses=ERROR_RESPONSES,
)
def reject_change_request(
    task_id: UUID,
    change_request_id: UUID,
    request: TaskChangeRequestRejectRequest,
    actor: Actor,
    service: TaskService,
) -> TaskChangeRequestActionResponse:
    return _change_request_response(
        service.reject_change_request(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            change_request_id,
            request.reason,
        )
    )


@router.post(
    "/{task_id}/change-requests/{change_request_id}/actions/cancel",
    response_model=TaskChangeRequestActionResponse,
    summary="Cancel a pending task change request",
    responses=ERROR_RESPONSES,
)
def cancel_change_request(
    task_id: UUID,
    change_request_id: UUID,
    request: CancelTaskChangeRequest,
    actor: Actor,
    service: TaskService,
) -> TaskChangeRequestActionResponse:
    return _change_request_response(
        service.cancel_change_request(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            change_request_id,
            request.reason,
        )
    )


@router.post(
    "/{task_id}/actions/cancel",
    response_model=TaskActionResponse,
    summary="Cancel a task",
    responses=ERROR_RESPONSES,
)
def cancel_task(
    task_id: UUID,
    request: ReasonTaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.cancel_task(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.reason,
        )
    )


@router.post(
    "/{task_id}/actions/withdraw",
    response_model=TaskActionResponse,
    summary="Withdraw a task",
    responses=ERROR_RESPONSES,
)
def withdraw_task(
    task_id: UUID,
    request: ReasonTaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.withdraw_task(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.reason,
        )
    )


@router.post(
    "/{task_id}/actions/close",
    response_model=TaskActionResponse,
    summary="Close an invalid or obsolete task",
    responses=ERROR_RESPONSES,
)
def close_task(
    task_id: UUID,
    request: ReasonTaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.close_task(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.reason,
        )
    )


@router.post(
    "/{task_id}/actions/archive",
    response_model=TaskActionResponse,
    summary="Move a completed task to the archive-eligible state",
    responses=ERROR_RESPONSES,
)
def archive_task(
    task_id: UUID,
    request: TaskActionRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.archive_task(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
        )
    )


@router.post(
    "/{task_id}/actions/restore",
    response_model=TaskActionResponse,
    summary="Restore a task to a safe lifecycle state",
    responses=ERROR_RESPONSES,
)
def restore_task(
    task_id: UUID,
    request: RestoreTaskRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.restore_task(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.reason,
        )
    )


@router.post(
    "/{task_id}/actions/merge",
    response_model=TaskActionResponse,
    summary="Merge a task into another task without deleting its history",
    responses=ERROR_RESPONSES,
)
def merge_task(
    task_id: UUID,
    request: MergeTaskRequest,
    actor: Actor,
    service: TaskService,
) -> TaskActionResponse:
    return _task_response(
        service.merge_task(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.target_task_id,
            request.reason,
        )
    )


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
    response_model=CompletionReviewActionResponse,
    summary="Submit a completed task for review",
    responses=ERROR_RESPONSES,
)
def submit_completion(
    task_id: UUID,
    request: SubmitCompletionRequest,
    actor: Actor,
    service: TaskService,
) -> CompletionReviewActionResponse:
    return _completion_response(
        service.submit_completion(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.completion_note,
            request.deliverable_summary,
        )
    )


@router.post(
    "/{task_id}/actions/approve-completion",
    response_model=CompletionReviewActionResponse,
    summary="Approve task completion",
    responses=ERROR_RESPONSES,
)
def approve_completion(
    task_id: UUID,
    request: CompletionDecisionRequest,
    actor: Actor,
    service: TaskService,
) -> CompletionReviewActionResponse:
    return _completion_response(
        service.approve_completion(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.completion_review_id,
        )
    )


@router.post(
    "/{task_id}/actions/reject-completion",
    response_model=CompletionReviewActionResponse,
    summary="Reject task completion for overall or node rework",
    responses=ERROR_RESPONSES,
)
def reject_completion(
    task_id: UUID,
    request: RejectCompletionRequest,
    actor: Actor,
    service: TaskService,
) -> CompletionReviewActionResponse:
    return _completion_response(
        service.reject_completion(
            task_id,
            actor,
            request.expected_task_version,
            OPERATION_SOURCE,
            request.completion_review_id,
            request.reject_reason,
            request.rework_node_id,
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


@router.post(
    "/{task_id}/nodes/{node_id}/actions/reopen",
    response_model=NodeActionResponse,
    summary="Explicitly reopen the node selected by a rejected review",
    responses=ERROR_RESPONSES,
)
def reopen_node(
    task_id: UUID,
    node_id: UUID,
    request: ReopenNodeRequest,
    actor: Actor,
    service: NodeService,
    query_service: QueryService,
) -> NodeActionResponse:
    service.reopen_node(
        task_id,
        node_id,
        actor,
        request.expected_task_version,
        OPERATION_SOURCE,
        request.completion_review_id,
    )
    return _node_response(task_id, node_id, actor, query_service)
