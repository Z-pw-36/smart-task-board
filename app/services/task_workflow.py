from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.db.unit_of_work import UnitOfWork
from app.models import (
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

TASK_DRAFT = "draft"
TASK_PENDING_CONFIRMATION = "pending_confirmation"
TASK_PENDING_ACCEPTANCE = "pending_acceptance"
TASK_RETURNED = "returned"
TASK_IN_PROGRESS = "in_progress"
TASK_PENDING_REVIEW = "pending_review"
TASK_COMPLETED = "completed"

PARTICIPANT_CONFIRM_PENDING = "pending"
PARTICIPANT_CONFIRM_ACCEPTED = "accepted"
PARTICIPANT_CONFIRM_RETURNED = "returned"


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
        raise InvalidStateTransitionError(
            f"operation requires task status {expected_status}"
        )


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
    return uow.task_status_logs.add(log)


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


class TaskWorkflowService:
    """Orchestrate task-level Phase 4 state transitions atomically."""

    def __init__(self, uow_factory: UowFactory, clock: Clock = utc_now) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    def create_task_draft(self, command: CreateTaskDraftCommand) -> Task:
        now = _aware_utc(self._clock(), "clock")
        task_name = _required_text(command.task_name, "task_name")
        _required_text(command.operation_source, "operation_source")
        self._validate_task_numbers(command)
        node_by_id = self._validate_draft_nodes(command)
        validate_dependency_graph(
            node_by_id,
            (
                (item.predecessor_node_id, item.successor_node_id)
                for item in command.dependencies
            ),
        )

        with self._uow_factory() as uow:
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
                raise BusinessValidationError(
                    "self-assigned task must use confirm_self_assigned"
                )
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
                raise PermissionDeniedError(
                    "actor must also be the task main assignee"
                )
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
            latest_rejected = uow.task_completion_reviews.get_latest_rejected(
                task.task_id
            )
            if (
                latest_rejected is not None
                and latest_rejected.rework_node_id is not None
            ):
                if latest_rejected.reviewed_task_version is None:
                    raise BusinessValidationError(
                        "rejected completion review is missing its reviewed version"
                    )
                was_reopened = (
                    uow.task_status_logs.has_action_for_business_ref(
                        task.task_id,
                        "node_reopened",
                        "completion_review",
                        latest_rejected.completion_review_id,
                        after_task_version=(
                            latest_rejected.reviewed_task_version
                        ),
                    )
                )
                if not was_reopened:
                    raise InvalidStateTransitionError(
                        "the rejected rework node must be explicitly reopened"
                    )
                rework_node = next(
                    (
                        node
                        for node in nodes
                        if node.node_id == latest_rejected.rework_node_id
                    ),
                    None,
                )
                if rework_node is None:
                    raise BusinessValidationError(
                        "the rejected rework node does not belong to the task"
                    )
                if (
                    rework_node.status != "completed"
                    or rework_node.progress_percent != 100
                ):
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
                    raise BusinessValidationError(
                        "rework task node does not belong to the task"
                    )
                if rework_node.status != "completed":
                    raise InvalidStateTransitionError(
                        "rework requires a completed task node"
                    )
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
            node.status != "completed" or node.progress_percent != 100
            for node in nodes
        ):
            raise BusinessValidationError(
                "all task nodes must be completed at 100 percent"
            )

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
                raise BusinessValidationError(
                    "only the main assignee projection can be primary"
                )
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
                raise BusinessValidationError(
                    "node participant must reference a task node"
                )
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
                    raise BusinessValidationError(
                        f"node {field_name} must not be negative"
                    )
            start = _optional_utc(node.planned_start_time, "planned_start_time")
            deadline = _optional_utc(node.planned_deadline, "planned_deadline")
            if start is not None and deadline is not None and deadline < start:
                raise BusinessValidationError(
                    "planned deadline must not precede planned start"
                )
            node_by_id[node.node_id] = node
        return node_by_id
