from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.schemas.common import (
    DecimalString,
    NonNegativeDecimalString,
    StrictSchema,
    TaskNodeStatus,
    TaskStatus,
)

NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _require_aware(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("datetime must include a timezone")
    return value


class TaskNodeDraftRequest(StrictSchema):
    node_id: UUID
    node_order: int = Field(ge=1)
    node_name: NonBlankString
    sort_weight: int = 0
    action_detail: str | None = None
    tools_or_materials: str | None = None
    owner_employee_no: str | None = None
    planned_start_time: datetime | None = None
    planned_deadline: datetime | None = None
    estimated_hours: NonNegativeDecimalString | None = None
    actual_hours: NonNegativeDecimalString | None = None
    deliverable: str | None = None
    acceptance_criteria: str | None = None

    _validate_planned_start = field_validator("planned_start_time")(_require_aware)
    _validate_planned_deadline = field_validator("planned_deadline")(_require_aware)

    @model_validator(mode="after")
    def validate_time_order(self) -> "TaskNodeDraftRequest":
        if (
            self.planned_start_time is not None
            and self.planned_deadline is not None
            and self.planned_deadline < self.planned_start_time
        ):
            raise ValueError("planned_deadline must not precede planned_start_time")
        return self


class TaskPlanningNodeDraftRequest(TaskNodeDraftRequest):
    enabled: bool = True


class TaskNodeDependencyDraftRequest(StrictSchema):
    predecessor_node_id: UUID
    successor_node_id: UUID
    dependency_type: NonBlankString = "finish_to_start"
    dependency_id: UUID = Field(default_factory=uuid4)


class TaskNodeParticipantDraftRequest(StrictSchema):
    node_id: UUID
    employee_no: NonBlankString
    participant_role: NonBlankString


class UpdateNodeProgressRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    progress_percent: int = Field(ge=0, le=100)
    actual_hours: NonNegativeDecimalString | None = None


class TaskPlanningSuggestionRequest(StrictSchema):
    instructions: str | None = None


class TaskPlanningSuggestionNodeResponse(StrictSchema):
    client_node_id: str
    node_order: int
    node_name: str
    action_detail: str | None = None
    tools_or_materials: str | None = None
    suggested_owner_employee_no: str | None = None
    planned_start_time: datetime | None = None
    planned_deadline: datetime | None = None
    estimated_hours: DecimalString | None = None
    deliverable: str | None = None
    acceptance_criteria: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    enabled: bool = True


class TaskPlanningSuggestionDependencyResponse(StrictSchema):
    predecessor_client_node_id: str
    successor_client_node_id: str
    dependency_type: str
    reason: str | None = None


class TaskPlanningSuggestionResponse(StrictSchema):
    task_id: UUID
    suggested_nodes: list[TaskPlanningSuggestionNodeResponse]
    suggested_dependencies: list[TaskPlanningSuggestionDependencyResponse]


class ConfirmTaskPlanningRequest(StrictSchema):
    expected_task_version: int = Field(ge=1)
    nodes: tuple[TaskPlanningNodeDraftRequest, ...]
    dependencies: tuple[TaskNodeDependencyDraftRequest, ...] = ()
    node_participants: tuple[TaskNodeParticipantDraftRequest, ...] = ()


class TaskNodeResponse(StrictSchema):
    node_id: UUID
    task_id: UUID
    node_order: int
    sort_weight: int
    node_name: str
    action_detail: str | None
    tools_or_materials: str | None
    owner_employee_no: str | None
    planned_start_time: datetime | None
    planned_deadline: datetime | None
    estimated_hours: DecimalString | None
    actual_hours: DecimalString | None
    deliverable: str | None
    acceptance_criteria: str | None
    progress_percent: int
    status: TaskNodeStatus
    completed_at: datetime | None


class TaskNodeDependencyResponse(StrictSchema):
    dependency_id: UUID
    task_id: UUID
    predecessor_node_id: UUID
    successor_node_id: UUID
    dependency_type: str


class TaskNodeParticipantResponse(StrictSchema):
    node_participant_id: UUID
    task_id: UUID
    node_id: UUID
    employee_no: str
    participant_role: str


class NodeActionResponse(StrictSchema):
    task_id: UUID
    node_id: UUID
    task_status: TaskStatus
    node_status: TaskNodeStatus
    progress_percent: int
    task_version: int
