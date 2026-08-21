from __future__ import annotations

import copy
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.db.unit_of_work import UnitOfWork
from app.models import (
    OperationLog,
    Task,
    TaskCompletionReview,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskStatusLog,
)
from app.services.clock import Clock, utc_now
from app.services.commands import CreateTaskDraftCommand
from app.services.dependency_graph import validate_dependency_graph
from app.services.errors import (
    BusinessValidationError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    OpenTaskIssueConflictError,
    PermissionDeniedError,
    TaskVersionConflictError,
)

UowFactory = Callable[[], UnitOfWork]


class _UniqueViolation(Exception):
    sqlstate = "23505"

TASK_DRAFT = "draft"
TASK_PENDING_CONFIRMATION = "pending_confirmation"
TASK_PENDING_ACCEPTANCE = "pending_acceptance"
TASK_RETURNED = "returned"
TASK_IN_PROGRESS = "in_progress"
TASK_PENDING_REVIEW = "pending_review"
TASK_COMPLETED = "completed"
TASK_ARCHIVED = "archived"
TASK_CANCELLED = "cancelled"
TASK_WITHDRAWN = "withdrawn"
TASK_MERGED = "merged"
TASK_CLOSED = "closed"

PARTICIPANT_CONFIRM_PENDING = "pending"
PARTICIPANT_CONFIRM_ACCEPTED = "accepted"
PARTICIPANT_CONFIRM_RETURNED = "returned"

# A change request may alter confirmed facts and structure, but never identity,
# lifecycle state, or optimistic-lock metadata.  The lists intentionally mirror
# the fields exposed by TaskQueryService and the node/participant repositories.
_CHANGEABLE_TASK_FIELDS = frozenset(
    {
        "task_name",
        "task_description",
        "task_goal",
        "task_source",
        "main_assignee_employee_no",
        "report_to_employee_no",
        "report_to_level",
        "reviewer_employee_no",
        "department_id",
        "start_time",
        "deadline",
        "estimated_hours",
        "actual_hours",
        "task_weight",
        "deliverable",
        "acceptance_criteria",
        "is_urgent",
        "report_cycle",
    }
)
_STRUCTURAL_CHANGE_FIELDS = frozenset(
    {"nodes", "dependencies", "participants", "node_participants"}
)
_CHANGEABLE_FIELDS = _CHANGEABLE_TASK_FIELDS | _STRUCTURAL_CHANGE_FIELDS
_STRUCTURAL_ID_FIELDS = {
    "nodes": "node_id",
    "dependencies": "dependency_id",
    "participants": "participant_id",
    "node_participants": "node_participant_id",
}
_REPORT_CYCLE_RE = re.compile(
    r"^weekly:(MON|TUE|WED|THU|FRI|SAT|SUN)@([01][0-9]|2[0-3]):[0-5][0-9]$"
)


def _aware_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BusinessValidationError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _optional_utc(value: datetime | None, field_name: str) -> datetime | None:
    return None if value is None else _aware_utc(value, field_name)


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise BusinessValidationError(f"{field_name} must not be blank")
    return normalized


def _lock_task(
    uow: UnitOfWork,
    task_id: UUID,
    expected_task_version: int,
) -> Task:
    task = uow.tasks.get_by_id_for_update(task_id)
    if task is None:
        raise EntityNotFoundError("task was not found")
    if task.task_version != expected_task_version:
        raise TaskVersionConflictError("task version does not match")
    return task


def _require_state(task: Task, expected_status: str) -> None:
    if task.status != expected_status:
        raise InvalidStateTransitionError(f"operation requires task status {expected_status}")


def _require_actor(actual: str, expected: str | None, role_name: str) -> None:
    if expected is None or actual != expected:
        raise PermissionDeniedError(f"actor must be the task {role_name}")


def _append_log(
    uow: UnitOfWork,
    task: Task,
    *,
    from_status: str | None,
    to_status: str,
    action_type: str,
    operator_employee_no: str,
    operation_source: str,
    now: datetime,
    reason: str | None = None,
    target_employee_no: str | None = None,
    business_ref_type: str | None = None,
    business_ref_id: UUID | None = None,
) -> TaskStatusLog:
    log = TaskStatusLog(
        task_id=task.task_id,
        from_status=from_status,
        to_status=to_status,
        action_type=action_type,
        reason=reason,
        operator_employee_no=operator_employee_no,
        target_employee_no=target_employee_no,
        task_version=task.task_version,
        business_ref_type=business_ref_type,
        business_ref_id=business_ref_id,
        operation_source=_required_text(operation_source, "operation_source"),
        created_at=now,
    )
    saved_log = uow.task_status_logs.add(log)
    session = getattr(uow, "session", None)
    if session is not None:
        session.add(
            OperationLog(
                operator_employee_no=operator_employee_no,
                action=action_type,
                object_type=business_ref_type or "task",
                object_id=str(business_ref_id or task.task_id),
                before_data={
                    "status": from_status,
                    "task_version": (
                        task.task_version if from_status == to_status else task.task_version - 1
                    ),
                },
                after_data={"status": to_status, "task_version": task.task_version},
                result="success",
                created_at=now,
            )
        )
    return saved_log


def _increment_task(task: Task, now: datetime) -> None:
    task.task_version += 1
    task.updated_at = now


def _primary_assignee_participant(
    uow: UnitOfWork,
    task: Task,
) -> TaskParticipant:
    employee_no = task.main_assignee_employee_no
    if employee_no is None:
        raise BusinessValidationError("task must have a main assignee")
    participant = uow.tasks.find_participant(
        task.task_id,
        employee_no,
        "assignee",
    )
    if participant is None or not participant.is_primary:
        raise BusinessValidationError("primary assignee projection is missing")
    return participant


def _validate_existing_graph(uow: UnitOfWork, task_id: UUID) -> list[TaskNode]:
    nodes = uow.task_nodes.list_nodes(task_id)
    dependencies = uow.task_nodes.list_dependencies(task_id)
    validate_dependency_graph(
        (node.node_id for node in nodes),
        (
            (dependency.predecessor_node_id, dependency.successor_node_id)
            for dependency in dependencies
        ),
    )
    return nodes


def _json_value(value: object) -> object:
    """Convert ORM values to values accepted by a JSON/JSONB column."""
    if isinstance(value, (UUID,)):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return value


def _uuid_value(value: object, field_name: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise BusinessValidationError(f"{field_name} must be a UUID") from exc


def _patch_operation(path: str, value: object) -> tuple[str, object]:
    """Accept a small JSON-Patch-shaped form in addition to a mapping patch."""
    normalized_path = path.strip().lstrip("/").replace("/", ".")
    if normalized_path.startswith("task."):
        normalized_path = normalized_path[5:]
    if not normalized_path or "." in normalized_path:
        raise BusinessValidationError("change patch paths must name one field")
    return normalized_path, value


def _generate_missing_structure_ids(field: str, value: object) -> object:
    """Fill server-generated IDs for structural add/replace patches."""
    id_field = _STRUCTURAL_ID_FIELDS.get(field)
    if id_field is None:
        return copy.deepcopy(value)

    def normalize_item(item: object) -> dict[str, object]:
        if not isinstance(item, Mapping):
            raise BusinessValidationError(f"{field} entries must be objects")
        normalized_item = copy.deepcopy(dict(item))
        if not normalized_item.get(id_field):
            normalized_item[id_field] = str(uuid4())
        return normalized_item

    if isinstance(value, Mapping):
        normalized_value = copy.deepcopy(dict(value))
        for operation in ("add", "replace"):
            if operation not in normalized_value:
                continue
            entries = normalized_value[operation]
            if not isinstance(entries, Sequence) or isinstance(
                entries, (str, bytes, bytearray)
            ):
                raise BusinessValidationError(f"{field}.{operation} must be a list")
            normalized_value[operation] = [normalize_item(item) for item in entries]
        return normalized_value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_item(item) for item in value]
    return copy.deepcopy(value)


def _normalize_change_fields(
    change_fields: Mapping[str, object] | Sequence[object],
) -> dict[str, object]:
    """Normalize supported change-request payloads without mutating caller data."""
    if isinstance(change_fields, Mapping):
        source: object = change_fields
        # A common API spelling is {"task": {...}, "nodes": ...}.  Flatten the
        # task object while retaining structural collections at the top level.
        if set(change_fields) <= {
            "task",
            "nodes",
            "dependencies",
            "participants",
            "node_participants",
        } and isinstance(change_fields.get("task"), Mapping):
            source = {
                **change_fields["task"],
                **{key: value for key, value in change_fields.items() if key != "task"},
            }
        items = list(source.items()) if isinstance(source, Mapping) else []
    elif isinstance(change_fields, Sequence) and not isinstance(
        change_fields, (str, bytes, bytearray)
    ):
        items = []
        for item in change_fields:
            if not isinstance(item, Mapping):
                raise BusinessValidationError("change patch operations must be objects")
            operation = str(item.get("op", "replace")).lower()
            if operation not in {"replace", "add", "remove"}:
                raise BusinessValidationError("unsupported change patch operation")
            path = item.get("path")
            if not isinstance(path, str):
                raise BusinessValidationError("change patch operation path is required")
            field, value = _patch_operation(path, item.get("value"))
            if operation == "remove":
                value = None
            items.append((field, value))
    else:
        raise BusinessValidationError("change_fields must be an object or patch list")

    normalized: dict[str, object] = {}
    for key, value in items:
        field = str(key)
        if field.startswith("/"):
            field, value = _patch_operation(field, value)
        if field not in _CHANGEABLE_FIELDS:
            raise BusinessValidationError(f"field {field} cannot be changed")
        if field in normalized:
            raise BusinessValidationError(f"duplicate change for field {field}")
        normalized[field] = _generate_missing_structure_ids(field, value)
    if not normalized:
        raise BusinessValidationError("change_fields must not be empty")
    return normalized


class TaskWorkflowService:
    """Orchestrate task-level Phase 4 state transitions atomically."""

    def __init__(self, uow_factory: UowFactory, clock: Clock = utc_now) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    # ------------------------------------------------------------------
    # Wave 2: immutable change requests
    # ------------------------------------------------------------------
    def create_change_request(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        change_fields: Mapping[str, object] | Sequence[object] | None = None,
        change_reason: str | None = None,
        *,
        changes: Mapping[str, object] | Sequence[object] | None = None,
        reason: str | None = None,
        change_request_id: UUID | None = None,
    ) -> object:
        """Create a pending, immutable task-change proposal.

        The request itself does not advance the task version.  Its base version
        and complete before/after snapshots make stale approval and audit
        behaviour deterministic.
        """
        patch = change_fields if change_fields is not None else changes
        if patch is None:
            raise BusinessValidationError("change_fields is required")
        normalized_reason = _required_text(
            change_reason if change_reason is not None else reason or "",
            "change_reason",
        )
        normalized_source = _required_text(operation_source, "operation_source")
        normalized_patch = _normalize_change_fields(patch)

        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            self._require_change_requester(uow, task, actor_employee_no)
            requests = getattr(uow, "task_change_requests", None)
            if requests is None:
                raise BusinessValidationError("task change requests are unavailable")
            pending = requests.get_pending_for_update(task.task_id)
            if pending is not None:
                raise InvalidStateTransitionError("task already has a pending change request")
            before = self._task_snapshot(uow, task)
            after = self._candidate_snapshot(uow, task, normalized_patch)
            self._validate_candidate(uow, task, normalized_patch, after)
            now = _aware_utc(self._clock(), "clock")
            request = self._new_change_request(
                task=task,
                request_id=change_request_id or uuid4(),
                actor_employee_no=actor_employee_no,
                patch=normalized_patch,
                reason=normalized_reason,
                before=before,
                after=after,
                now=now,
            )
            requests.add(request)
            # Creation is an auditable action at the current task version; no
            # task fact is changed until approval.
            _append_log(
                uow,
                task,
                from_status=task.status,
                to_status=task.status,
                action_type="change_requested",
                operator_employee_no=actor_employee_no,
                target_employee_no=task.creator_employee_no,
                operation_source=normalized_source,
                reason=normalized_reason,
                now=now,
                business_ref_type="task_change_request",
                business_ref_id=request.change_request_id,
            )
            uow.commit()
            return task, request

    def submit_change_request(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        patch_json: Mapping[str, object] | Sequence[object],
        reason: str,
        change_request_id: UUID | None = None,
    ) -> object:
        """Submit the canonical API form of an immutable change request."""
        return self.create_change_request(
            task_id,
            actor_employee_no,
            expected_task_version,
            operation_source,
            change_fields=patch_json,
            change_reason=reason,
            change_request_id=change_request_id,
        )

    def approve_change_request(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        change_request_id: UUID,
        approval_comment: str | None = None,
        *,
        comment: str | None = None,
    ) -> tuple[Task, object]:
        normalized_source = _required_text(operation_source, "operation_source")
        normalized_comment = (
            None
            if approval_comment is None and comment is None
            else _required_text(
                approval_comment if approval_comment is not None else comment or "",
                "approval_comment",
            )
        )
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            self._require_change_decider(task, actor_employee_no)
            request = self._lock_change_request(uow, task, change_request_id)
            self._require_pending_change_request(request, task)
            patch = _normalize_change_fields(request.patch_json)
            after = self._candidate_snapshot(uow, task, patch)
            self._validate_candidate(uow, task, patch, after)
            now = _aware_utc(self._clock(), "clock")
            self._apply_candidate(uow, task, patch, after)
            _increment_task(task, now)
            request.status = "approved"
            request.decision_by_employee_no = actor_employee_no
            request.decision_comment = normalized_comment
            request.decision_at = now
            _append_log(
                uow,
                task,
                from_status=task.status,
                to_status=task.status,
                action_type="change_approved",
                operator_employee_no=actor_employee_no,
                operation_source=normalized_source,
                reason=normalized_comment,
                now=now,
                business_ref_type="task_change_request",
                business_ref_id=request.change_request_id,
            )
            uow.commit()
            return task, request

    def reject_change_request(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        change_request_id: UUID,
        reject_reason: str | None = None,
        *,
        reason: str | None = None,
    ) -> object:
        normalized_reason = _required_text(
            reject_reason if reject_reason is not None else reason or "",
            "reject_reason",
        )
        normalized_source = _required_text(operation_source, "operation_source")
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            self._require_change_decider(task, actor_employee_no)
            request = self._lock_change_request(uow, task, change_request_id)
            self._require_pending_change_request(request, task)
            now = _aware_utc(self._clock(), "clock")
            request.status = "rejected"
            request.decision_by_employee_no = actor_employee_no
            request.decision_comment = normalized_reason
            request.decision_at = now
            _append_log(
                uow,
                task,
                from_status=task.status,
                to_status=task.status,
                action_type="change_rejected",
                operator_employee_no=actor_employee_no,
                operation_source=normalized_source,
                reason=normalized_reason,
                now=now,
                business_ref_type="task_change_request",
                business_ref_id=request.change_request_id,
            )
            uow.commit()
            return task, request

    def cancel_change_request(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        change_request_id: UUID,
        cancel_reason: str | None = None,
        *,
        reason: str | None = None,
    ) -> object:
        normalized_reason = _required_text(
            cancel_reason if cancel_reason is not None else reason or "",
            "cancel_reason",
        )
        normalized_source = _required_text(operation_source, "operation_source")
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            request = self._lock_change_request(uow, task, change_request_id)
            self._require_pending_change_request(request, task)
            if request.requester_employee_no != actor_employee_no:
                raise PermissionDeniedError("actor must be the change requester")
            now = _aware_utc(self._clock(), "clock")
            request.status = "cancelled"
            request.cancelled_by_employee_no = actor_employee_no
            request.cancellation_reason = normalized_reason
            request.cancelled_at = now
            _append_log(
                uow,
                task,
                from_status=task.status,
                to_status=task.status,
                action_type="change_cancelled",
                operator_employee_no=actor_employee_no,
                operation_source=normalized_source,
                reason=normalized_reason,
                now=now,
                business_ref_type="task_change_request",
                business_ref_id=request.change_request_id,
            )
            uow.commit()
            return task, request

    @staticmethod
    def _require_change_requester(
        uow: UnitOfWork,
        task: Task,
        actor_employee_no: str,
    ) -> None:
        if task.status != TASK_IN_PROGRESS:
            raise InvalidStateTransitionError("change requests require an in-progress task")
        if actor_employee_no != task.main_assignee_employee_no:
            raise PermissionDeniedError("actor must be the main task assignee")

    @staticmethod
    def _require_change_decider(task: Task, actor_employee_no: str) -> None:
        if actor_employee_no != task.creator_employee_no:
            raise PermissionDeniedError("actor must be the task creator")

    @staticmethod
    def _lock_change_request(
        uow: UnitOfWork,
        task: Task,
        change_request_id: UUID,
    ) -> object:
        requests = getattr(uow, "task_change_requests", None)
        if requests is None:
            raise BusinessValidationError("task change requests are unavailable")
        request = requests.get_by_task_and_id_for_update(
            task.task_id,
            change_request_id,
        )
        if request is None:
            raise EntityNotFoundError("task change request was not found")
        return request

    @staticmethod
    def _require_pending_change_request(request: object, task: Task) -> None:
        if request.status != "pending":
            raise InvalidStateTransitionError("task change request is no longer pending")
        if request.base_task_version != task.task_version:
            raise TaskVersionConflictError(
                "task change request is based on an obsolete task version"
            )

    @staticmethod
    def _task_snapshot(uow: UnitOfWork, task: Task) -> dict[str, object]:
        fields = (
            "task_id",
            "task_no",
            "task_name",
            "task_description",
            "task_goal",
            "task_source",
            "creator_employee_no",
            "main_assignee_employee_no",
            "report_to_employee_no",
            "report_to_level",
            "reviewer_employee_no",
            "department_id",
            "status",
            "start_time",
            "deadline",
            "estimated_hours",
            "actual_hours",
            "task_weight",
            "deliverable",
            "acceptance_criteria",
            "is_urgent",
            "report_cycle",
            "cancel_reason",
            "withdraw_reason",
            "close_reason",
            "merged_into_task_id",
            "task_version",
            "created_at",
            "updated_at",
            "confirmed_at",
            "sent_at",
            "accepted_at",
            "completed_at",
            "archived_at",
        )
        snapshot: dict[str, object] = {
            field: _json_value(getattr(task, field, None)) for field in fields
        }
        nodes = uow.task_nodes.list_nodes(task.task_id)
        dependencies = uow.task_nodes.list_dependencies(task.task_id)
        participants = uow.tasks.list_participants(task.task_id)
        node_participants_method = getattr(
            uow.task_nodes,
            "list_participants_by_task_id",
            None,
        )
        node_participants = (
            node_participants_method(task.task_id) if node_participants_method is not None else []
        )
        snapshot["nodes"] = [
            {
                key: _json_value(getattr(node, key, None))
                for key in (
                    "node_id",
                    "task_id",
                    "node_order",
                    "sort_weight",
                    "node_name",
                    "action_detail",
                    "tools_or_materials",
                    "owner_employee_no",
                    "planned_start_time",
                    "planned_deadline",
                    "estimated_hours",
                    "actual_hours",
                    "deliverable",
                    "acceptance_criteria",
                    "progress_percent",
                    "status",
                    "completed_at",
                )
            }
            for node in nodes
        ]
        snapshot["dependencies"] = [
            {
                key: _json_value(getattr(dependency, key, None))
                for key in (
                    "dependency_id",
                    "task_id",
                    "predecessor_node_id",
                    "successor_node_id",
                    "dependency_type",
                )
            }
            for dependency in dependencies
        ]
        snapshot["participants"] = [
            {
                key: _json_value(getattr(participant, key, None))
                for key in (
                    "participant_id",
                    "task_id",
                    "employee_no",
                    "participant_role",
                    "is_primary",
                    "confirm_status",
                    "confirmed_at",
                )
            }
            for participant in participants
        ]
        snapshot["node_participants"] = [
            {
                key: _json_value(getattr(participant, key, None))
                for key in (
                    "node_participant_id",
                    "task_id",
                    "node_id",
                    "employee_no",
                    "participant_role",
                )
            }
            for participant in node_participants
        ]
        return snapshot

    def _candidate_snapshot(
        self,
        uow: UnitOfWork,
        task: Task,
        patch: Mapping[str, object],
    ) -> dict[str, object]:
        candidate = copy.deepcopy(self._task_snapshot(uow, task))
        for field, value in patch.items():
            if field in _CHANGEABLE_TASK_FIELDS:
                candidate[field] = self._normalize_task_patch_value(field, value)
            else:
                candidate[field] = self._normalize_structure_patch(
                    field,
                    value,
                    candidate[field],
                )
        return candidate

    @staticmethod
    def _normalize_task_patch_value(field: str, value: object) -> object:
        if field in {
            "task_name",
            "task_description",
            "task_goal",
            "task_source",
            "deliverable",
            "acceptance_criteria",
            "report_to_level",
        }:
            if value is None and field != "task_name":
                return None
            if not isinstance(value, str):
                raise BusinessValidationError(f"{field} must be text")
            return _required_text(value, field) if field == "task_name" else value
        if field in {"start_time", "deadline"}:
            if value is None:
                return None
            if isinstance(value, datetime):
                return _aware_utc(value, field).isoformat()
            if isinstance(value, str):
                try:
                    return _aware_utc(datetime.fromisoformat(value), field).isoformat()
                except ValueError as exc:
                    raise BusinessValidationError(f"{field} must be ISO datetime") from exc
            raise BusinessValidationError(f"{field} must be timezone-aware datetime")
        if field in {"estimated_hours", "actual_hours"}:
            if value is None:
                return None
            try:
                number = Decimal(str(value))
            except (ArithmeticError, ValueError) as exc:
                raise BusinessValidationError(f"{field} must be numeric") from exc
            if number < 0:
                raise BusinessValidationError(f"{field} must not be negative")
            return str(number)
        if field == "task_weight":
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
                raise BusinessValidationError("task_weight must be between 1 and 5")
            return value
        if field in {"is_urgent"}:
            if value is not None and not isinstance(value, bool):
                raise BusinessValidationError(f"{field} must be boolean")
            return value
        if field == "report_cycle":
            if value is not None and (
                not isinstance(value, str) or not _REPORT_CYCLE_RE.fullmatch(value)
            ):
                raise BusinessValidationError("report_cycle has an invalid format")
            return value
        if field in {
            "main_assignee_employee_no",
            "report_to_employee_no",
            "reviewer_employee_no",
        }:
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise BusinessValidationError(f"{field} must be an employee number")
            return value
        if field == "department_id":
            return None if value is None else str(_uuid_value(value, field))
        return _json_value(value)

    @staticmethod
    def _normalize_structure_patch(
        field: str,
        value: object,
        current: object,
    ) -> list[dict[str, object]]:
        if not isinstance(value, (Mapping, Sequence)) or isinstance(value, (str, bytes, bytearray)):
            raise BusinessValidationError(f"{field} patch must be a list or object")
        if isinstance(value, Mapping):
            operations = value
            if not any(key in operations for key in ("add", "update", "remove", "replace")):
                raise BusinessValidationError(f"{field} patch has no operations")
            result = copy.deepcopy(current if isinstance(current, list) else [])
            if "replace" in operations:
                replacement = operations["replace"]
                if not isinstance(replacement, Sequence) or isinstance(
                    replacement, (str, bytes, bytearray)
                ):
                    raise BusinessValidationError(f"{field}.replace must be a list")
                result = copy.deepcopy(list(replacement))
            for key in ("remove", "update", "add"):
                if key not in operations:
                    continue
                values = operations[key]
                if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
                    raise BusinessValidationError(f"{field}.{key} must be a list")
                if key == "remove":
                    ids = {
                        str(item.get("id", item)) if isinstance(item, Mapping) else str(item)
                        for item in values
                    }
                    id_field = {
                        "nodes": "node_id",
                        "dependencies": "dependency_id",
                        "participants": "participant_id",
                        "node_participants": "node_participant_id",
                    }[field]
                    result = [item for item in result if str(item.get(id_field)) not in ids]
                elif key == "update":
                    id_field = {
                        "nodes": "node_id",
                        "dependencies": "dependency_id",
                        "participants": "participant_id",
                        "node_participants": "node_participant_id",
                    }[field]
                    by_id = {str(item.get(id_field)): item for item in result}
                    for item in values:
                        if not isinstance(item, Mapping) or id_field not in item:
                            raise BusinessValidationError(f"{field}.update items need {id_field}")
                        item_id = str(item[id_field])
                        if item_id not in by_id:
                            raise EntityNotFoundError(f"{field} update target was not found")
                        by_id[item_id].update(copy.deepcopy(dict(item)))
                else:
                    result.extend(copy.deepcopy(list(values)))
            return [dict(item) for item in result if isinstance(item, Mapping)]
        return [dict(item) for item in value if isinstance(item, Mapping)]

    def _validate_candidate(
        self,
        uow: UnitOfWork,
        task: Task,
        patch: Mapping[str, object],
        candidate: Mapping[str, object],
    ) -> None:
        start = candidate.get("start_time")
        deadline = candidate.get("deadline")
        if start is not None and deadline is not None:
            if datetime.fromisoformat(str(deadline)) < datetime.fromisoformat(str(start)):
                raise BusinessValidationError("deadline must not precede start_time")
        nodes = candidate.get("nodes", [])
        dependencies = candidate.get("dependencies", [])
        node_ids = {
            _uuid_value(item.get("node_id"), "node_id")
            for item in nodes
            if isinstance(item, Mapping)
        }
        if len(node_ids) != len(nodes):
            raise BusinessValidationError("duplicate node_id")
        node_orders: set[int] = set()
        for item in nodes:
            if not isinstance(item, Mapping):
                raise BusinessValidationError("node entries must be objects")
            try:
                node_order = int(item.get("node_order"))
            except (TypeError, ValueError) as exc:
                raise BusinessValidationError("node_order must be positive") from exc
            if node_order < 1 or node_order in node_orders:
                raise BusinessValidationError("node_order must be positive and unique")
            node_orders.add(node_order)
            node_start = item.get("planned_start_time")
            node_deadline = item.get("planned_deadline")
            if node_start is not None and node_deadline is not None:
                if datetime.fromisoformat(str(node_deadline)) < datetime.fromisoformat(
                    str(node_start)
                ):
                    raise BusinessValidationError("planned deadline must not precede planned start")
            for field in ("estimated_hours", "actual_hours"):
                value = item.get(field)
                if value is not None:
                    try:
                        if Decimal(str(value)) < 0:
                            raise BusinessValidationError(f"node {field} must not be negative")
                    except (ArithmeticError, ValueError) as exc:
                        raise BusinessValidationError(f"node {field} must be numeric") from exc
        edges: list[tuple[UUID, UUID]] = []
        seen_dependencies: set[tuple[UUID, UUID, str]] = set()
        for item in dependencies:
            if not isinstance(item, Mapping):
                raise BusinessValidationError("dependency entries must be objects")
            predecessor = _uuid_value(item.get("predecessor_node_id"), "predecessor_node_id")
            successor = _uuid_value(item.get("successor_node_id"), "successor_node_id")
            dependency_type = str(item.get("dependency_type", "finish_to_start"))
            if predecessor not in node_ids or successor not in node_ids:
                raise BusinessValidationError("dependency must reference nodes in the task")
            key = (predecessor, successor, dependency_type)
            if key in seen_dependencies:
                raise BusinessValidationError("duplicate dependency")
            seen_dependencies.add(key)
            edges.append((predecessor, successor))
        validate_dependency_graph(node_ids, edges)
        if ("nodes" in patch or "dependencies" in patch) and not nodes:
            raise BusinessValidationError("task must have at least one node")
        self._validate_candidate_structure(uow, task, candidate, node_ids, patch)
        self._validate_candidate_people(uow, task, candidate)

    @staticmethod
    def _validate_candidate_structure(
        uow: UnitOfWork,
        task: Task,
        candidate: Mapping[str, object],
        node_ids: set[UUID],
        patch: Mapping[str, object],
    ) -> None:
        if "nodes" in patch:
            current_nodes = {node.node_id: node for node in uow.task_nodes.list_nodes(task.task_id)}
            candidate_nodes = {
                _uuid_value(item.get("node_id"), "node_id"): item
                for item in candidate.get("nodes", [])
                if isinstance(item, Mapping)
            }
            for node_id, current_node in current_nodes.items():
                candidate_node = candidate_nodes.get(node_id)
                if candidate_node is None:
                    if current_node.status == "completed":
                        raise InvalidStateTransitionError("completed task nodes cannot be deleted")
                    continue
                if current_node.status == "completed" and (
                    candidate_node.get("status") != "completed"
                    or int(candidate_node.get("progress_percent", 0)) != 100
                ):
                    raise InvalidStateTransitionError(
                        "completed task nodes cannot be reopened by a change request"
                    )

        participants = candidate.get("participants", [])
        participant_keys: set[tuple[str, str]] = set()
        primary_assignee: str | None = None
        for item in participants:
            if not isinstance(item, Mapping):
                raise BusinessValidationError("participant entries must be objects")
            employee_no = item.get("employee_no")
            role = item.get("participant_role")
            if not isinstance(employee_no, str) or not employee_no.strip():
                raise BusinessValidationError("participant employee_no is required")
            if not isinstance(role, str) or not role.strip():
                raise BusinessValidationError("participant_role must not be blank")
            key = (employee_no, role)
            if key in participant_keys:
                raise BusinessValidationError("duplicate task participant")
            participant_keys.add(key)
            if bool(item.get("is_primary", False)):
                if role != "assignee" or primary_assignee is not None:
                    raise BusinessValidationError(
                        "only one primary assignee participant is allowed"
                    )
                primary_assignee = employee_no
        main_assignee = candidate.get("main_assignee_employee_no")
        if (
            ("participants" in patch or participants)
            and main_assignee is not None
            and primary_assignee != main_assignee
        ):
            raise BusinessValidationError(
                "main assignee must have the primary assignee participant"
            )
        node_participant_keys: set[tuple[UUID, str, str]] = set()
        for item in candidate.get("node_participants", []):
            if not isinstance(item, Mapping):
                raise BusinessValidationError("node participant entries must be objects")
            node_id = _uuid_value(item.get("node_id"), "node_id")
            employee_no = item.get("employee_no")
            role = item.get("participant_role")
            if node_id not in node_ids:
                raise BusinessValidationError("node participant must reference a task node")
            if not isinstance(employee_no, str) or not employee_no.strip():
                raise BusinessValidationError("node participant employee_no is required")
            if not isinstance(role, str) or not role.strip():
                raise BusinessValidationError("participant_role must not be blank")
            key = (node_id, employee_no, role)
            if key in node_participant_keys:
                raise BusinessValidationError("duplicate task node participant")
            node_participant_keys.add(key)

    @staticmethod
    def _validate_candidate_people(
        uow: UnitOfWork,
        task: Task,
        candidate: Mapping[str, object],
    ) -> None:
        department_id = candidate.get("department_id")
        if (
            department_id is not None
            and uow.departments.get_by_id(_uuid_value(department_id, "department_id")) is None
        ):
            raise EntityNotFoundError("department was not found")
        employee_numbers: set[str] = set()
        for field in (
            "creator_employee_no",
            "main_assignee_employee_no",
            "report_to_employee_no",
            "reviewer_employee_no",
        ):
            value = candidate.get(field)
            if isinstance(value, str):
                employee_numbers.add(value)
        for collection_name, employee_field in (
            ("participants", "employee_no"),
            ("nodes", "owner_employee_no"),
            ("node_participants", "employee_no"),
        ):
            for item in candidate.get(collection_name, []):
                if isinstance(item, Mapping) and isinstance(item.get(employee_field), str):
                    employee_numbers.add(str(item[employee_field]))
        for employee_no in employee_numbers:
            if uow.users.get_by_employee_no(employee_no) is None:
                raise EntityNotFoundError("user was not found")

    def _apply_candidate(
        self,
        uow: UnitOfWork,
        task: Task,
        patch: Mapping[str, object],
        candidate: Mapping[str, object],
    ) -> None:
        for field in patch:
            if field in _CHANGEABLE_TASK_FIELDS:
                value = candidate[field]
                if field in {"start_time", "deadline"} and value is not None:
                    value = datetime.fromisoformat(str(value))
                elif field in {"estimated_hours", "actual_hours"} and value is not None:
                    value = Decimal(str(value))
                elif field == "department_id" and value is not None:
                    value = _uuid_value(value, field)
                setattr(task, field, value)
        # Apply dependent rows before nodes so foreign-key restrictions do not
        # turn a valid structural patch into a partial transaction.
        for field in (
            "dependencies",
            "node_participants",
            "participants",
            "nodes",
        ):
            if field not in patch:
                continue
            self._apply_structure(uow, task, field, candidate[field])

    @staticmethod
    def _apply_structure(
        uow: UnitOfWork,
        task: Task,
        field: str,
        desired: object,
    ) -> None:
        if not isinstance(desired, list):
            return
        if field == "nodes":
            repository = uow.task_nodes
            current = {str(item.node_id): item for item in repository.list_nodes(task.task_id)}
            desired_ids = {
                str(item.get("node_id"))
                for item in desired
                if isinstance(item, Mapping) and item.get("node_id") is not None
            }
            for key, existing in current.items():
                if key not in desired_ids:
                    repository.delete_node(existing)
            for item in desired:
                if not isinstance(item, Mapping) or "node_id" not in item:
                    raise BusinessValidationError("node entries need node_id")
                key = str(item["node_id"])
                existing = current.get(key)
                if existing is None:
                    values = TaskWorkflowService._node_values(item)
                    repository.add_node(
                        TaskNode(
                            task_id=task.task_id,
                            node_id=_uuid_value(item["node_id"], "node_id"),
                            **values,
                        )
                    )
                else:
                    for key_name, value in TaskWorkflowService._node_values(item).items():
                        if hasattr(existing, key_name):
                            setattr(existing, key_name, value)
            return
        if field == "dependencies":
            repository = uow.task_nodes
            current = {
                str(item.dependency_id): item for item in repository.list_dependencies(task.task_id)
            }
            desired_ids = {
                str(item.get("dependency_id"))
                for item in desired
                if isinstance(item, Mapping) and item.get("dependency_id") is not None
            }
            for key, existing in current.items():
                if key not in desired_ids:
                    repository.delete_dependency(existing)
            for item in desired:
                if not isinstance(item, Mapping):
                    raise BusinessValidationError("dependency entries must be objects")
                key = str(item.get("dependency_id", ""))
                existing = current.get(key)
                values = {
                    "predecessor_node_id": _uuid_value(
                        item.get("predecessor_node_id"), "predecessor_node_id"
                    ),
                    "successor_node_id": _uuid_value(
                        item.get("successor_node_id"), "successor_node_id"
                    ),
                    "dependency_type": str(item.get("dependency_type", "finish_to_start")),
                }
                if existing is None:
                    repository.add_dependency(
                        TaskNodeDependency(
                            task_id=task.task_id,
                            dependency_id=_uuid_value(item.get("dependency_id"), "dependency_id"),
                            **values,
                        )
                    )
                else:
                    for key_name, value in values.items():
                        setattr(existing, key_name, value)
            return
        if field == "participants":
            repository = uow.tasks
            current = {
                str(item.participant_id): item
                for item in repository.list_participants(task.task_id)
            }
            desired_ids = {
                str(item.get("participant_id"))
                for item in desired
                if isinstance(item, Mapping) and item.get("participant_id") is not None
            }
            for key, existing in current.items():
                if key not in desired_ids:
                    repository.delete_participant(existing)
            for item in desired:
                if not isinstance(item, Mapping):
                    raise BusinessValidationError("participant entries must be objects")
                key = str(item.get("participant_id", ""))
                existing = current.get(key)
                values = {
                    "employee_no": str(item["employee_no"]),
                    "participant_role": str(item["participant_role"]),
                    "is_primary": bool(item.get("is_primary", False)),
                }
                if existing is None:
                    repository.add_participant(
                        TaskParticipant(
                            task_id=task.task_id,
                            participant_id=_uuid_value(
                                item.get("participant_id"), "participant_id"
                            ),
                            **values,
                        )
                    )
                else:
                    for key_name, value in values.items():
                        setattr(existing, key_name, value)
            return
        repository = uow.task_nodes
        list_method = getattr(repository, "list_participants_by_task_id", None)
        current_items = list_method(task.task_id) if list_method is not None else []
        current = {str(item.node_participant_id): item for item in current_items}
        desired_ids = {
            str(item.get("node_participant_id"))
            for item in desired
            if isinstance(item, Mapping) and item.get("node_participant_id") is not None
        }
        for key, existing in current.items():
            if key not in desired_ids:
                repository.delete_participant(existing)
        for item in desired:
            if not isinstance(item, Mapping):
                raise BusinessValidationError("node participant entries must be objects")
            key = str(item.get("node_participant_id", ""))
            existing = current.get(key)
            values = {
                "node_id": _uuid_value(item.get("node_id"), "node_id"),
                "employee_no": str(item["employee_no"]),
                "participant_role": str(item["participant_role"]),
            }
            if existing is None:
                repository.add_participant(
                    TaskNodeParticipant(
                        task_id=task.task_id,
                        node_participant_id=_uuid_value(
                            item.get("node_participant_id"), "node_participant_id"
                        ),
                        **values,
                    )
                )
            else:
                for key_name, value in values.items():
                    setattr(existing, key_name, value)

    @staticmethod
    def _node_values(item: Mapping[str, object]) -> dict[str, object]:
        values: dict[str, object] = {}
        datetime_fields = {
            "planned_start_time",
            "planned_deadline",
            "completed_at",
        }
        decimal_fields = {"estimated_hours", "actual_hours"}
        integer_fields = {"node_order", "sort_weight", "progress_percent"}
        for key, value in item.items():
            if key in {"node_id", "task_id"}:
                continue
            if key in datetime_fields and value is not None:
                value = datetime.fromisoformat(str(value))
            elif key in decimal_fields and value is not None:
                value = Decimal(str(value))
            elif key in integer_fields and value is not None:
                value = int(value)
            values[key] = value
        return values

    @staticmethod
    def _new_change_request(
        *,
        task: Task,
        request_id: UUID,
        actor_employee_no: str,
        patch: Mapping[str, object],
        reason: str,
        before: Mapping[str, object],
        after: Mapping[str, object],
        now: datetime,
    ) -> object:
        try:
            from app.models import TaskChangeRequest
        except ImportError as exc:
            raise BusinessValidationError("task change request model is unavailable") from exc
        return TaskChangeRequest(
            change_request_id=request_id,
            task_id=task.task_id,
            requester_employee_no=actor_employee_no,
            patch_json=_json_value(dict(patch)),
            reason=reason,
            before_snapshot=_json_value(before),
            after_snapshot=_json_value(after),
            status="pending",
            requester_task_version=task.task_version,
            base_task_version=task.task_version,
            created_at=now,
        )

    # ------------------------------------------------------------------
    # Wave 2: complete task lifecycle
    # ------------------------------------------------------------------
    def cancel_task(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        reason: str,
    ) -> Task:
        return self._lifecycle_transition(
            task_id,
            actor_employee_no,
            expected_task_version,
            operation_source,
            reason=reason,
            action_type="task_cancelled",
            to_status=TASK_CANCELLED,
            from_statuses={
                TASK_DRAFT,
                TASK_PENDING_CONFIRMATION,
                TASK_PENDING_ACCEPTANCE,
                TASK_RETURNED,
                TASK_IN_PROGRESS,
                TASK_PENDING_REVIEW,
            },
            authority="admin",
        )

    def withdraw_task(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        reason: str,
    ) -> Task:
        return self._lifecycle_transition(
            task_id,
            actor_employee_no,
            expected_task_version,
            operation_source,
            reason=reason,
            action_type="task_withdrawn",
            to_status=TASK_WITHDRAWN,
            from_statuses={
                TASK_PENDING_ACCEPTANCE,
                TASK_RETURNED,
                TASK_IN_PROGRESS,
                TASK_PENDING_REVIEW,
            },
            authority="assignee",
        )

    def close_task(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        reason: str,
    ) -> Task:
        return self._lifecycle_transition(
            task_id,
            actor_employee_no,
            expected_task_version,
            operation_source,
            reason=reason,
            action_type="task_closed",
            to_status=TASK_CLOSED,
            from_statuses={TASK_COMPLETED, TASK_IN_PROGRESS, TASK_PENDING_REVIEW},
            authority="admin",
            require_closed_issues=True,
        )

    def archive_task(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
    ) -> Task:
        return self._lifecycle_transition(
            task_id,
            actor_employee_no,
            expected_task_version,
            operation_source,
            reason=None,
            action_type="task_archived",
            to_status=TASK_ARCHIVED,
            from_statuses={TASK_COMPLETED},
            authority="admin",
        )

    def restore_task(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        reason: str | None = None,
    ) -> Task:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            self._require_change_decider(task, actor_employee_no)
            if task.status == TASK_MERGED:
                raise InvalidStateTransitionError("merged tasks cannot be restored")
            restore_status = {
                TASK_CANCELLED: TASK_PENDING_CONFIRMATION,
                TASK_CLOSED: TASK_PENDING_CONFIRMATION,
                TASK_WITHDRAWN: TASK_PENDING_CONFIRMATION,
                TASK_ARCHIVED: TASK_COMPLETED,
            }.get(task.status)
            if restore_status is None:
                raise InvalidStateTransitionError("task status is not eligible for restore")
            normalized_source = _required_text(operation_source, "operation_source")
            normalized_reason = _required_text(reason, "reason") if reason is not None else None
            now = _aware_utc(self._clock(), "clock")
            previous_status = task.status
            task.status = restore_status
            if previous_status == TASK_ARCHIVED:
                task.archived_at = None
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=previous_status,
                to_status=restore_status,
                action_type="task_restored",
                operator_employee_no=actor_employee_no,
                operation_source=normalized_source,
                reason=normalized_reason,
                now=now,
            )
            uow.commit()
            return task

    def merge_task(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        target_task_id: UUID,
        reason: str | None = None,
        target_expected_task_version: int | None = None,
    ) -> Task:
        if task_id == target_task_id:
            raise BusinessValidationError("a task cannot be merged into itself")
        normalized_source = _required_text(operation_source, "operation_source")
        normalized_reason = _required_text(reason, "reason") if reason is not None else None
        with self._uow_factory() as uow:
            # Lock both aggregates before mutating either.  The source version
            # is mandatory; callers may provide the target version when they
            # need a strict cross-task compare-and-swap as well.
            lock_ids = sorted((task_id, target_task_id), key=str)
            locked_tasks = {
                lock_id: uow.tasks.get_by_id_for_update(lock_id) for lock_id in lock_ids
            }
            source = locked_tasks[task_id]
            target = locked_tasks[target_task_id]
            if source is None or target is None:
                raise EntityNotFoundError("task was not found")
            if source.task_version != expected_task_version:
                raise TaskVersionConflictError("task version does not match")
            if (
                target_expected_task_version is not None
                and target.task_version != target_expected_task_version
            ):
                raise TaskVersionConflictError("target task version does not match")
            self._require_change_decider(source, actor_employee_no)
            if source.status in {TASK_ARCHIVED, TASK_CANCELLED, TASK_WITHDRAWN, TASK_MERGED}:
                raise InvalidStateTransitionError("source task cannot be merged")
            if target.status in {TASK_ARCHIVED, TASK_CANCELLED, TASK_WITHDRAWN, TASK_MERGED}:
                raise InvalidStateTransitionError("target task cannot receive a merge")
            now = _aware_utc(self._clock(), "clock")
            previous_status = source.status
            source.status = TASK_MERGED
            source.merged_into_task_id = target.task_id
            _increment_task(source, now)
            self._cancel_pending_requests(
                uow,
                source,
                actor_employee_no,
                "task was merged",
                now,
            )
            _append_log(
                uow,
                source,
                from_status=previous_status,
                to_status=TASK_MERGED,
                action_type="task_merged",
                operator_employee_no=actor_employee_no,
                target_employee_no=target.creator_employee_no,
                operation_source=normalized_source,
                reason=normalized_reason or f"merged_into:{target.task_id}",
                now=now,
                business_ref_type="task",
                business_ref_id=target.task_id,
            )
            uow.commit()
            return source

    # Short aliases are useful to command handlers and preserve the verbs used
    # in the product requirements without duplicating transition logic.
    cancel = cancel_task
    withdraw = withdraw_task
    close = close_task
    archive = archive_task
    restore = restore_task
    merge = merge_task

    def _lifecycle_transition(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        *,
        reason: str | None,
        action_type: str,
        to_status: str,
        from_statuses: set[str],
        authority: str,
        require_closed_issues: bool = False,
    ) -> Task:
        normalized_source = _required_text(operation_source, "operation_source")
        normalized_reason = None if reason is None else _required_text(reason, "reason")
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            if task.status not in from_statuses:
                raise InvalidStateTransitionError(
                    f"operation is not allowed from task status {task.status}"
                )
            if authority == "assignee":
                if actor_employee_no != task.main_assignee_employee_no:
                    raise PermissionDeniedError("actor must be the main task assignee")
            else:
                self._require_change_decider(task, actor_employee_no)
            if require_closed_issues and uow.task_issues.has_non_closed(task.task_id):
                raise OpenTaskIssueConflictError(
                    "all task issues must be closed before closing the task"
                )
            previous_status = task.status
            now = _aware_utc(self._clock(), "clock")
            task.status = to_status
            if to_status == TASK_CANCELLED:
                task.cancel_reason = normalized_reason
            elif to_status == TASK_WITHDRAWN:
                task.withdraw_reason = normalized_reason
            elif to_status == TASK_CLOSED:
                task.close_reason = normalized_reason
            elif to_status == TASK_ARCHIVED:
                task.archived_at = now
            _increment_task(task, now)
            self._cancel_pending_requests(
                uow,
                task,
                actor_employee_no,
                f"task transitioned to {to_status}",
                now,
            )
            _append_log(
                uow,
                task,
                from_status=previous_status,
                to_status=to_status,
                action_type=action_type,
                operator_employee_no=actor_employee_no,
                operation_source=normalized_source,
                reason=normalized_reason,
                now=now,
            )
            uow.commit()
            return task

    @staticmethod
    def _archived_previous_status(uow: UnitOfWork, task: Task) -> str:
        logs = getattr(uow.task_status_logs, "list_by_task_id", None)
        if logs is not None:
            history = logs(task.task_id)
            for log in reversed(history):
                if log.action_type == "task_archived":
                    return log.from_status or TASK_COMPLETED
        return TASK_COMPLETED

    @staticmethod
    def _cancel_pending_requests(
        uow: UnitOfWork,
        task: Task,
        actor_employee_no: str,
        reason: str,
        now: datetime,
    ) -> None:
        requests = getattr(uow, "task_change_requests", None)
        if requests is None:
            return
        pending = requests.get_pending(task.task_id)
        if pending is None:
            return
        pending.status = "cancelled"
        pending.cancelled_by_employee_no = actor_employee_no
        pending.cancellation_reason = reason
        pending.cancelled_at = now

    def create_task_draft(self, command: CreateTaskDraftCommand) -> Task:
        now = _aware_utc(self._clock(), "clock")
        task_name = _required_text(command.task_name, "task_name")
        _required_text(command.operation_source, "operation_source")
        self._validate_task_numbers(command)
        node_by_id = self._validate_draft_nodes(command)
        validate_dependency_graph(
            node_by_id,
            ((item.predecessor_node_id, item.successor_node_id) for item in command.dependencies),
        )

        with self._uow_factory() as uow:
            existing = uow.tasks.get_by_id_for_update(command.task_id)
            if isinstance(existing, Task):
                if existing.creator_employee_no != command.creator_employee_no:
                    raise BusinessValidationError("task_id is already used by another creator")
                if command.extraction_record_ids:
                    raise IntegrityError(
                        "duplicate task_id",
                        {"task_id": command.task_id},
                        _UniqueViolation("tasks.task_id already exists"),
                    )
                return existing
            self._require_user(uow, command.creator_employee_no)
            for employee_no in {
                command.main_assignee_employee_no,
                command.report_to_employee_no,
                command.reviewer_employee_no,
            } - {None}:
                self._require_user(uow, employee_no)
            if (
                command.department_id is not None
                and uow.departments.get_by_id(command.department_id) is None
            ):
                raise EntityNotFoundError("department was not found")

            participant_keys = self._validate_task_participants(uow, command)
            self._validate_node_people(uow, command, node_by_id)

            task = Task(
                task_id=command.task_id,
                task_no=None,
                task_name=task_name,
                task_description=command.task_description,
                task_goal=command.task_goal,
                task_source=command.task_source,
                creator_employee_no=command.creator_employee_no,
                main_assignee_employee_no=command.main_assignee_employee_no,
                report_to_employee_no=command.report_to_employee_no,
                report_to_level=command.report_to_level,
                reviewer_employee_no=command.reviewer_employee_no,
                department_id=command.department_id,
                status=TASK_DRAFT,
                start_time=_optional_utc(command.start_time, "start_time"),
                deadline=_optional_utc(command.deadline, "deadline"),
                estimated_hours=command.estimated_hours,
                actual_hours=command.actual_hours,
                task_weight=command.task_weight,
                deliverable=command.deliverable,
                acceptance_criteria=command.acceptance_criteria,
                is_urgent=command.is_urgent,
                report_cycle=command.report_cycle,
                task_version=1,
                created_at=now,
                updated_at=now,
            )
            uow.tasks.add(task)

            if command.main_assignee_employee_no is not None:
                uow.tasks.add_participant(
                    TaskParticipant(
                        task_id=task.task_id,
                        employee_no=command.main_assignee_employee_no,
                        participant_role="assignee",
                        is_primary=True,
                    )
                )
            for participant in command.participants:
                uow.tasks.add_participant(
                    TaskParticipant(
                        task_id=task.task_id,
                        employee_no=participant.employee_no,
                        participant_role=participant.participant_role,
                        is_primary=participant.is_primary,
                    )
                )
            if len(participant_keys) != len(command.participants) + (
                1 if command.main_assignee_employee_no is not None else 0
            ):
                raise BusinessValidationError("duplicate task participant")

            for node in command.nodes:
                uow.task_nodes.add_node(
                    TaskNode(
                        node_id=node.node_id,
                        task_id=task.task_id,
                        node_order=node.node_order,
                        sort_weight=node.sort_weight,
                        node_name=node.node_name.strip(),
                        action_detail=node.action_detail,
                        tools_or_materials=node.tools_or_materials,
                        owner_employee_no=node.owner_employee_no,
                        planned_start_time=_optional_utc(
                            node.planned_start_time,
                            "planned_start_time",
                        ),
                        planned_deadline=_optional_utc(
                            node.planned_deadline,
                            "planned_deadline",
                        ),
                        estimated_hours=node.estimated_hours,
                        actual_hours=node.actual_hours,
                        deliverable=node.deliverable,
                        acceptance_criteria=node.acceptance_criteria,
                        progress_percent=0,
                        status="pending",
                    )
                )
            for dependency in command.dependencies:
                uow.task_nodes.add_dependency(
                    TaskNodeDependency(
                        dependency_id=dependency.dependency_id,
                        task_id=task.task_id,
                        predecessor_node_id=dependency.predecessor_node_id,
                        successor_node_id=dependency.successor_node_id,
                        dependency_type=dependency.dependency_type,
                    )
                )
            for participant in command.node_participants:
                uow.task_nodes.add_participant(
                    TaskNodeParticipant(
                        task_id=task.task_id,
                        node_id=participant.node_id,
                        employee_no=participant.employee_no,
                        participant_role=participant.participant_role,
                    )
                )

            extraction_ids: set[UUID] = set()
            for extraction_id in command.extraction_record_ids:
                if extraction_id in extraction_ids:
                    raise BusinessValidationError("duplicate extraction record")
                extraction_ids.add(extraction_id)
                extraction = uow.ai_extraction_records.get_by_id(extraction_id)
                if extraction is None:
                    raise EntityNotFoundError("AI extraction record was not found")
                if extraction.task_id is not None:
                    raise BusinessValidationError(
                        "AI extraction record is already linked to a task"
                    )
                extraction.task_id = task.task_id
                extraction.confirmed_at = now

            _append_log(
                uow,
                task,
                from_status=None,
                to_status=TASK_DRAFT,
                action_type="task_created",
                operator_employee_no=command.creator_employee_no,
                operation_source=command.operation_source,
                now=now,
            )
            uow.commit()
            return task

    def submit_for_confirmation(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
    ) -> Task:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_DRAFT)
            _require_actor(actor_employee_no, task.creator_employee_no, "creator")
            _primary_assignee_participant(uow, task)
            nodes = _validate_existing_graph(uow, task.task_id)
            if not nodes:
                raise BusinessValidationError("task must have at least one node")
            now = _aware_utc(self._clock(), "clock")
            task.status = TASK_PENDING_CONFIRMATION
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_DRAFT,
                to_status=TASK_PENDING_CONFIRMATION,
                action_type="submitted_for_confirmation",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
            )
            uow.commit()
            return task

    def confirm_and_send(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
    ) -> Task:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_PENDING_CONFIRMATION)
            _require_actor(actor_employee_no, task.creator_employee_no, "creator")
            if task.main_assignee_employee_no == task.creator_employee_no:
                raise BusinessValidationError("self-assigned task must use confirm_self_assigned")
            participant = _primary_assignee_participant(uow, task)
            now = _aware_utc(self._clock(), "clock")
            task.status = TASK_PENDING_ACCEPTANCE
            task.confirmed_at = now
            task.sent_at = now
            participant.confirm_status = PARTICIPANT_CONFIRM_PENDING
            participant.confirmed_at = None
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_PENDING_CONFIRMATION,
                to_status=TASK_PENDING_ACCEPTANCE,
                action_type="confirmed_and_sent",
                operator_employee_no=actor_employee_no,
                target_employee_no=task.main_assignee_employee_no,
                operation_source=operation_source,
                now=now,
            )
            uow.commit()
            return task

    def confirm_self_assigned(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
    ) -> Task:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_PENDING_CONFIRMATION)
            _require_actor(actor_employee_no, task.creator_employee_no, "creator")
            if task.main_assignee_employee_no != actor_employee_no:
                raise PermissionDeniedError("actor must also be the task main assignee")
            participant = _primary_assignee_participant(uow, task)
            now = _aware_utc(self._clock(), "clock")
            task.status = TASK_IN_PROGRESS
            task.confirmed_at = now
            task.sent_at = now
            task.accepted_at = now
            participant.confirm_status = PARTICIPANT_CONFIRM_ACCEPTED
            participant.confirmed_at = now
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_PENDING_CONFIRMATION,
                to_status=TASK_IN_PROGRESS,
                action_type="self_assigned_confirmed",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
            )
            uow.commit()
            return task

    def accept_task(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
    ) -> Task:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_PENDING_ACCEPTANCE)
            _require_actor(
                actor_employee_no,
                task.main_assignee_employee_no,
                "main assignee",
            )
            participant = _primary_assignee_participant(uow, task)
            now = _aware_utc(self._clock(), "clock")
            task.status = TASK_IN_PROGRESS
            task.accepted_at = now
            participant.confirm_status = PARTICIPANT_CONFIRM_ACCEPTED
            participant.confirmed_at = now
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_PENDING_ACCEPTANCE,
                to_status=TASK_IN_PROGRESS,
                action_type="task_accepted",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
            )
            uow.commit()
            return task

    def return_task(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        reason: str,
    ) -> Task:
        normalized_reason = _required_text(reason, "reason")
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_PENDING_ACCEPTANCE)
            _require_actor(
                actor_employee_no,
                task.main_assignee_employee_no,
                "main assignee",
            )
            participant = _primary_assignee_participant(uow, task)
            now = _aware_utc(self._clock(), "clock")
            task.status = TASK_RETURNED
            participant.confirm_status = PARTICIPANT_CONFIRM_RETURNED
            participant.confirmed_at = None
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_PENDING_ACCEPTANCE,
                to_status=TASK_RETURNED,
                action_type="task_returned",
                operator_employee_no=actor_employee_no,
                target_employee_no=task.creator_employee_no,
                operation_source=operation_source,
                reason=normalized_reason,
                now=now,
            )
            uow.commit()
            return task

    def resend_task(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
    ) -> Task:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_RETURNED)
            _require_actor(actor_employee_no, task.creator_employee_no, "creator")
            participant = _primary_assignee_participant(uow, task)
            now = _aware_utc(self._clock(), "clock")
            task.status = TASK_PENDING_ACCEPTANCE
            task.sent_at = now
            participant.confirm_status = PARTICIPANT_CONFIRM_PENDING
            participant.confirmed_at = None
            _increment_task(task, now)
            _append_log(
                uow,
                task,
                from_status=TASK_RETURNED,
                to_status=TASK_PENDING_ACCEPTANCE,
                action_type="task_resent",
                operator_employee_no=actor_employee_no,
                target_employee_no=task.main_assignee_employee_no,
                operation_source=operation_source,
                now=now,
            )
            uow.commit()
            return task

    def submit_completion(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        completion_note: str,
        deliverable_summary: str,
    ) -> tuple[Task, TaskCompletionReview]:
        normalized_note = _required_text(completion_note, "completion_note")
        normalized_summary = _required_text(
            deliverable_summary,
            "deliverable_summary",
        )
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_IN_PROGRESS)
            _require_actor(
                actor_employee_no,
                task.main_assignee_employee_no,
                "main assignee",
            )
            nodes = _validate_existing_graph(uow, task.task_id)
            self._require_completed_nodes(nodes)
            if uow.task_issues.has_non_closed(task.task_id):
                raise OpenTaskIssueConflictError(
                    "all task issues must be closed before submitting completion"
                )
            latest_rejected = uow.task_completion_reviews.get_latest_rejected(task.task_id)
            if latest_rejected is not None and latest_rejected.rework_node_id is not None:
                if latest_rejected.reviewed_task_version is None:
                    raise BusinessValidationError(
                        "rejected completion review is missing its reviewed version"
                    )
                was_reopened = uow.task_status_logs.has_action_for_business_ref(
                    task.task_id,
                    "node_reopened",
                    "completion_review",
                    latest_rejected.completion_review_id,
                    after_task_version=(latest_rejected.reviewed_task_version),
                )
                if not was_reopened:
                    raise InvalidStateTransitionError(
                        "the rejected rework node must be explicitly reopened"
                    )
                rework_node = next(
                    (node for node in nodes if node.node_id == latest_rejected.rework_node_id),
                    None,
                )
                if rework_node is None:
                    raise BusinessValidationError(
                        "the rejected rework node does not belong to the task"
                    )
                if rework_node.status != "completed" or rework_node.progress_percent != 100:
                    raise BusinessValidationError(
                        "the reopened rework node must be completed at 100 percent"
                    )
            now = _aware_utc(self._clock(), "clock")
            review_round = uow.task_completion_reviews.next_round(task.task_id)
            reviewer = task.reviewer_employee_no or task.creator_employee_no
            task.status = TASK_PENDING_REVIEW
            _increment_task(task, now)
            review = TaskCompletionReview(
                completion_review_id=uuid4(),
                task_id=task.task_id,
                review_round=review_round,
                submitted_by_employee_no=actor_employee_no,
                completion_note=normalized_note,
                deliverable_summary=normalized_summary,
                reviewer_employee_no=reviewer,
                review_status="submitted",
                submitted_task_version=task.task_version,
                submitted_at=now,
                is_legacy_import=False,
            )
            uow.task_completion_reviews.add(review)
            _append_log(
                uow,
                task,
                from_status=TASK_IN_PROGRESS,
                to_status=TASK_PENDING_REVIEW,
                action_type="completion_submitted",
                operator_employee_no=actor_employee_no,
                target_employee_no=reviewer,
                operation_source=operation_source,
                now=now,
                business_ref_type="completion_review",
                business_ref_id=review.completion_review_id,
            )
            uow.commit()
            return task, review

    def approve_completion(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        completion_review_id: UUID,
    ) -> tuple[Task, TaskCompletionReview]:
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_PENDING_REVIEW)
            review = self._lock_submitted_review(
                uow,
                task,
                completion_review_id,
            )
            _require_actor(
                actor_employee_no,
                review.reviewer_employee_no,
                "reviewer",
            )
            nodes = _validate_existing_graph(uow, task.task_id)
            self._require_completed_nodes(nodes)
            now = _aware_utc(self._clock(), "clock")
            task.status = TASK_COMPLETED
            task.completed_at = now
            _increment_task(task, now)
            review.review_status = "approved"
            review.review_result = "approved"
            review.reviewed_at = now
            review.reviewed_task_version = task.task_version
            _append_log(
                uow,
                task,
                from_status=TASK_PENDING_REVIEW,
                to_status=TASK_COMPLETED,
                action_type="completion_approved",
                operator_employee_no=actor_employee_no,
                operation_source=operation_source,
                now=now,
                business_ref_type="completion_review",
                business_ref_id=review.completion_review_id,
            )
            uow.commit()
            return task, review

    def reject_completion(
        self,
        task_id: UUID,
        actor_employee_no: str,
        expected_task_version: int,
        operation_source: str,
        completion_review_id: UUID,
        reject_reason: str,
        rework_node_id: UUID | None = None,
    ) -> tuple[Task, TaskCompletionReview]:
        normalized_reason = _required_text(reject_reason, "reject_reason")
        with self._uow_factory() as uow:
            task = _lock_task(uow, task_id, expected_task_version)
            _require_state(task, TASK_PENDING_REVIEW)
            review = self._lock_submitted_review(
                uow,
                task,
                completion_review_id,
            )
            _require_actor(
                actor_employee_no,
                review.reviewer_employee_no,
                "reviewer",
            )
            if rework_node_id is not None:
                rework_node = uow.task_nodes.get_node(rework_node_id)
                if rework_node is None:
                    raise EntityNotFoundError("rework task node was not found")
                if rework_node.task_id != task.task_id:
                    raise BusinessValidationError("rework task node does not belong to the task")
                if rework_node.status != "completed":
                    raise InvalidStateTransitionError("rework requires a completed task node")
            now = _aware_utc(self._clock(), "clock")
            task.status = TASK_IN_PROGRESS
            task.completed_at = None
            _increment_task(task, now)
            review.review_status = "rejected"
            review.review_result = "rejected"
            review.reject_reason = normalized_reason
            review.rework_node_id = rework_node_id
            review.reviewed_at = now
            review.reviewed_task_version = task.task_version
            _append_log(
                uow,
                task,
                from_status=TASK_PENDING_REVIEW,
                to_status=TASK_IN_PROGRESS,
                action_type="completion_rejected",
                operator_employee_no=actor_employee_no,
                target_employee_no=task.main_assignee_employee_no,
                operation_source=operation_source,
                reason=normalized_reason,
                now=now,
                business_ref_type="completion_review",
                business_ref_id=review.completion_review_id,
            )
            uow.commit()
            return task, review

    @staticmethod
    def _lock_submitted_review(
        uow: UnitOfWork,
        task: Task,
        completion_review_id: UUID,
    ) -> TaskCompletionReview:
        review = uow.task_completion_reviews.get_by_task_and_id_for_update(
            task.task_id,
            completion_review_id,
        )
        if review is None:
            raise EntityNotFoundError("completion review was not found")
        if (
            review.review_status != "submitted"
            or review.submitted_task_version != task.task_version
        ):
            raise InvalidStateTransitionError(
                "completion review is not the current submitted round"
            )
        return review

    @staticmethod
    def _require_completed_nodes(nodes: list[TaskNode]) -> None:
        if not nodes or any(
            node.status != "completed" or node.progress_percent != 100 for node in nodes
        ):
            raise BusinessValidationError("all task nodes must be completed at 100 percent")

    @staticmethod
    def _require_user(uow: UnitOfWork, employee_no: str) -> None:
        if uow.users.get_by_employee_no(employee_no) is None:
            raise EntityNotFoundError("user was not found")

    def _validate_task_participants(
        self,
        uow: UnitOfWork,
        command: CreateTaskDraftCommand,
    ) -> set[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        if command.main_assignee_employee_no is not None:
            keys.add((command.main_assignee_employee_no, "assignee"))
        for participant in command.participants:
            self._require_user(uow, participant.employee_no)
            role = _required_text(participant.participant_role, "participant_role")
            if participant.is_primary:
                raise BusinessValidationError("only the main assignee projection can be primary")
            key = (participant.employee_no, role)
            if key in keys:
                raise BusinessValidationError("duplicate task participant")
            keys.add(key)
        return keys

    def _validate_node_people(
        self,
        uow: UnitOfWork,
        command: CreateTaskDraftCommand,
        node_by_id: dict[UUID, object],
    ) -> None:
        for node in command.nodes:
            if node.owner_employee_no is not None:
                self._require_user(uow, node.owner_employee_no)
        keys: set[tuple[UUID, str, str]] = set()
        for participant in command.node_participants:
            if participant.node_id not in node_by_id:
                raise BusinessValidationError("node participant must reference a task node")
            self._require_user(uow, participant.employee_no)
            role = _required_text(participant.participant_role, "participant_role")
            key = (participant.node_id, participant.employee_no, role)
            if key in keys:
                raise BusinessValidationError("duplicate task node participant")
            keys.add(key)

    @staticmethod
    def _validate_task_numbers(command: CreateTaskDraftCommand) -> None:
        for field_name, value in (
            ("estimated_hours", command.estimated_hours),
            ("actual_hours", command.actual_hours),
        ):
            if value is not None and value < Decimal(0):
                raise BusinessValidationError(f"{field_name} must not be negative")
        if command.task_weight is not None and not 1 <= command.task_weight <= 5:
            raise BusinessValidationError("task_weight must be between 1 and 5")

    @staticmethod
    def _validate_draft_nodes(
        command: CreateTaskDraftCommand,
    ) -> dict[UUID, object]:
        node_by_id: dict[UUID, object] = {}
        for node in command.nodes:
            if node.node_id in node_by_id:
                raise BusinessValidationError("duplicate node_id")
            if node.node_order < 1:
                raise BusinessValidationError("node_order must be positive")
            _required_text(node.node_name, "node_name")
            for field_name, value in (
                ("estimated_hours", node.estimated_hours),
                ("actual_hours", node.actual_hours),
            ):
                if value is not None and value < Decimal(0):
                    raise BusinessValidationError(f"node {field_name} must not be negative")
            start = _optional_utc(node.planned_start_time, "planned_start_time")
            deadline = _optional_utc(node.planned_deadline, "planned_deadline")
            if start is not None and deadline is not None and deadline < start:
                raise BusinessValidationError("planned deadline must not precede planned start")
            node_by_id[node.node_id] = node
        return node_by_id
