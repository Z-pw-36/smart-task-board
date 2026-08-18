from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class TaskParticipantDraft:
    employee_no: str
    participant_role: str
    is_primary: bool = False


@dataclass(frozen=True, slots=True)
class TaskNodeDraft:
    node_id: UUID
    node_order: int
    node_name: str
    sort_weight: int = 0
    action_detail: str | None = None
    tools_or_materials: str | None = None
    owner_employee_no: str | None = None
    planned_start_time: datetime | None = None
    planned_deadline: datetime | None = None
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    deliverable: str | None = None
    acceptance_criteria: str | None = None


@dataclass(frozen=True, slots=True)
class TaskNodeDependencyDraft:
    predecessor_node_id: UUID
    successor_node_id: UUID
    dependency_type: str = "finish_to_start"
    dependency_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class TaskNodeParticipantDraft:
    node_id: UUID
    employee_no: str
    participant_role: str


@dataclass(frozen=True, slots=True)
class CreateTaskDraftCommand:
    task_name: str
    creator_employee_no: str
    operation_source: str
    task_id: UUID = field(default_factory=uuid4)
    task_description: str | None = None
    task_goal: str | None = None
    task_source: str | None = None
    main_assignee_employee_no: str | None = None
    report_to_employee_no: str | None = None
    report_to_level: str | None = None
    reviewer_employee_no: str | None = None
    department_id: UUID | None = None
    start_time: datetime | None = None
    deadline: datetime | None = None
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    task_weight: int | None = None
    deliverable: str | None = None
    acceptance_criteria: str | None = None
    is_urgent: bool | None = None
    report_cycle: str | None = None
    participants: tuple[TaskParticipantDraft, ...] = ()
    nodes: tuple[TaskNodeDraft, ...] = ()
    dependencies: tuple[TaskNodeDependencyDraft, ...] = ()
    node_participants: tuple[TaskNodeParticipantDraft, ...] = ()
    extraction_record_ids: tuple[UUID, ...] = ()
