from collections.abc import Callable
from decimal import Decimal
from uuid import UUID

from app.db.unit_of_work import UnitOfWork
from app.models import Task, TaskNode
from app.services.clock import Clock, utc_now
from app.services.errors import (
    BusinessValidationError,
    DependencyNotSatisfiedError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    PermissionDeniedError,
)
from app.services.task_workflow import (
    TASK_IN_PROGRESS,
    _append_log,
    _aware_utc,
    _increment_task,
    _lock_task,
    _require_state,
)

UowFactory = Callable[[], UnitOfWork]


class TaskNodeWorkflowService:
    """Execute task nodes while preserving task version and audit invariants."""

    def __init__(self, uow_factory: UowFactory, clock: Clock = utc_now) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    def start_node(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
    ) -> TaskNode:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_IN_PROGRESS)
            node = self._task_node(uow, task, node_id)
            if node.status != "pending":
                raise InvalidStateTransitionError(
                    "start_node requires a pending task node"
                )
            self._require_node_actor(task, node, actor_employee_no)
            for dependency in uow.task_nodes.list_predecessors(task_id, node_id):
                predecessor = uow.task_nodes.get_node(
                    dependency.predecessor_node_id
                )
                if predecessor is None or predecessor.status != "completed":
                    raise DependencyNotSatisfiedError(
                        "all predecessor nodes must be completed"
                    )
            now = _aware_utc(self._clock(), "clock")
            node.status = "in_progress"
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_IN_PROGRESS,
                action_type="node_started",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
                business_ref_type="task_node",
                business_ref_id=node.node_id,
            )
            uow.commit()
            return node

    def update_node_progress(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        progress_percent: int,
        actual_hours: Decimal | None = None,
    ) -> TaskNode:
        if not 0 <= progress_percent <= 100:
            raise BusinessValidationError("progress_percent must be between 0 and 100")
        if actual_hours is not None and actual_hours < Decimal(0):
            raise BusinessValidationError("actual_hours must not be negative")
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_IN_PROGRESS)
            node = self._task_node(uow, task, node_id)
            if node.status != "in_progress":
                raise InvalidStateTransitionError(
                    "progress updates require an in-progress task node"
                )
            self._require_node_actor(task, node, actor_employee_no)
            if progress_percent < node.progress_percent:
                raise BusinessValidationError("node progress cannot decrease")
            if (
                actual_hours is not None
                and node.actual_hours is not None
                and actual_hours < node.actual_hours
            ):
                raise BusinessValidationError("node actual_hours cannot decrease")
            now = _aware_utc(self._clock(), "clock")
            node.progress_percent = progress_percent
            if actual_hours is not None:
                node.actual_hours = actual_hours
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_IN_PROGRESS,
                action_type="node_progress_updated",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
                business_ref_type="task_node",
                business_ref_id=node.node_id,
            )
            uow.commit()
            return node

    def complete_node(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
    ) -> TaskNode:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_IN_PROGRESS)
            node = self._task_node(uow, task, node_id)
            if node.status != "in_progress":
                raise InvalidStateTransitionError(
                    "complete_node requires an in-progress task node"
                )
            self._require_node_actor(task, node, actor_employee_no)
            now = _aware_utc(self._clock(), "clock")
            node.progress_percent = 100
            node.status = "completed"
            node.completed_at = now
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_IN_PROGRESS,
                action_type="node_completed",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
                business_ref_type="task_node",
                business_ref_id=node.node_id,
            )
            uow.commit()
            return node

    @staticmethod
    def _task_node(uow: UnitOfWork, task: Task, node_id: UUID) -> TaskNode:
        node = uow.task_nodes.get_node(node_id)
        if node is None:
            raise EntityNotFoundError("task node was not found")
        if node.task_id != task.task_id:
            raise BusinessValidationError("task node does not belong to the task")
        return node

    @staticmethod
    def _require_node_actor(
        task: Task,
        node: TaskNode,
        actor_employee_no: str,
    ) -> None:
        expected_actor = node.owner_employee_no or task.main_assignee_employee_no
        if expected_actor is None or actor_employee_no != expected_actor:
            raise PermissionDeniedError("actor cannot execute this task node")
