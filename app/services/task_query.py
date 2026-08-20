from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import (
    AIExtractionRecord,
    Task,
    TaskCompletionReview,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskStatusLog,
)
from app.repositories import (
    AIExtractionRecordRepository,
    TaskCompletionReviewRepository,
    TaskNodeRepository,
    TaskRepository,
    TaskStatusLogRepository,
)
from app.services.errors import (
    BusinessValidationError,
    EntityNotFoundError,
    PermissionDeniedError,
)


class TaskQueryService:
    """Read task projections without changing business or transaction state."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._tasks = TaskRepository(session)
        self._nodes = TaskNodeRepository(session)
        self._logs = TaskStatusLogRepository(session)
        self._completion_reviews = TaskCompletionReviewRepository(session)
        self._extractions = AIExtractionRecordRepository(session)

    def get_task_detail(self, task_id: UUID, actor_employee_no: str) -> dict[str, Any]:
        task, participants, nodes, dependencies, node_participants = self._aggregate(
            task_id,
            actor_employee_no,
        )
        result = self._task_dict(task)
        result.update(
            participants=[self._participant_dict(item) for item in participants],
            nodes=[self._node_dict(item) for item in nodes],
            dependencies=[self._dependency_dict(item) for item in dependencies],
            node_participants=[self._node_participant_dict(item) for item in node_participants],
            ai_extraction_records=[
                self._extraction_dict(item) for item in self._extractions.list_by_task_id(task_id)
            ],
        )
        return result

    def get_task_snapshot(self, task_id: UUID, actor_employee_no: str) -> dict[str, Any]:
        task, _, _, _, _ = self._aggregate(task_id, actor_employee_no)
        return {
            "task_id": task.task_id,
            "status": task.status,
            "task_version": task.task_version,
            "updated_at": task.updated_at,
        }

    def list_nodes(self, task_id: UUID, actor_employee_no: str) -> list[dict[str, Any]]:
        _, _, nodes, _, _ = self._aggregate(task_id, actor_employee_no)
        return [self._node_dict(node) for node in nodes]

    def get_node(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
    ) -> dict[str, Any]:
        self._aggregate(task_id, actor_employee_no)
        node = self._nodes.get_node(node_id)
        if node is None or node.task_id != task_id:
            raise EntityNotFoundError("task node was not found")
        return self._node_dict(node)

    def get_node_action_snapshot(
        self,
        task_id: UUID,
        node_id: UUID,
        actor_employee_no: str,
    ) -> dict[str, Any]:
        task, _, _, _, _ = self._aggregate(task_id, actor_employee_no)
        node = self._nodes.get_node(node_id)
        if node is None or node.task_id != task_id:
            raise EntityNotFoundError("task node was not found")
        return {
            "task_id": task.task_id,
            "node_id": node.node_id,
            "task_status": task.status,
            "node_status": node.status,
            "progress_percent": node.progress_percent,
            "task_version": task.task_version,
        }

    def list_status_logs(
        self,
        task_id: UUID,
        actor_employee_no: str,
        *,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise BusinessValidationError("limit must be between 1 and 100")
        if offset < 0:
            raise BusinessValidationError("offset must not be negative")
        self._aggregate(task_id, actor_employee_no)
        items = self._logs.list_by_task_id_paginated(
            task_id,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [self._status_log_dict(item) for item in items],
            "limit": limit,
            "offset": offset,
            "total": self._logs.count_by_task_id(task_id),
        }

    def list_completion_reviews(
        self,
        task_id: UUID,
        actor_employee_no: str,
        *,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise BusinessValidationError("limit must be between 1 and 100")
        if offset < 0:
            raise BusinessValidationError("offset must not be negative")
        self._require_task_read_access(task_id, actor_employee_no)
        items = self._completion_reviews.list_by_task_id(
            task_id,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [self._completion_review_dict(item) for item in items],
            "limit": limit,
            "offset": offset,
            "total": self._completion_reviews.count_by_task_id(task_id),
        }

    def get_completion_review(
        self,
        task_id: UUID,
        completion_review_id: UUID,
        actor_employee_no: str,
    ) -> dict[str, Any]:
        self._require_task_read_access(task_id, actor_employee_no)
        review = self._completion_reviews.get_by_id(completion_review_id)
        if review is None or review.task_id != task_id:
            raise EntityNotFoundError("completion review was not found")
        return self._completion_review_dict(review)

    def _require_task_read_access(
        self,
        task_id: UUID,
        actor_employee_no: str,
    ) -> Task:
        self._session.expire_all()
        task = self._tasks.get_by_id(task_id)
        if task is None:
            raise EntityNotFoundError("task was not found")
        if not self._tasks.is_related(task_id, actor_employee_no):
            raise PermissionDeniedError("actor cannot read this task")
        return task

    def _aggregate(
        self,
        task_id: UUID,
        actor_employee_no: str,
    ) -> tuple[
        Task,
        list[TaskParticipant],
        list[TaskNode],
        list[TaskNodeDependency],
        list[TaskNodeParticipant],
    ]:
        task = self._require_task_read_access(task_id, actor_employee_no)
        participants = self._tasks.list_participants(task_id)
        nodes = self._nodes.list_nodes(task_id)
        dependencies = self._nodes.list_dependencies(task_id)
        node_participants = self._nodes.list_participants_by_task_id(task_id)
        return task, participants, nodes, dependencies, node_participants

    @staticmethod
    def _task_dict(task: Task) -> dict[str, Any]:
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
        return {field: getattr(task, field) for field in fields}

    @staticmethod
    def _participant_dict(item: TaskParticipant) -> dict[str, Any]:
        return {
            "participant_id": item.participant_id,
            "task_id": item.task_id,
            "employee_no": item.employee_no,
            "participant_role": item.participant_role,
            "is_primary": item.is_primary,
            "confirm_status": item.confirm_status,
            "confirmed_at": item.confirmed_at,
        }

    @staticmethod
    def _node_dict(item: TaskNode) -> dict[str, Any]:
        fields = (
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
        return {field: getattr(item, field) for field in fields}

    @staticmethod
    def _dependency_dict(item: TaskNodeDependency) -> dict[str, Any]:
        return {
            "dependency_id": item.dependency_id,
            "task_id": item.task_id,
            "predecessor_node_id": item.predecessor_node_id,
            "successor_node_id": item.successor_node_id,
            "dependency_type": item.dependency_type,
        }

    @staticmethod
    def _node_participant_dict(item: TaskNodeParticipant) -> dict[str, Any]:
        return {
            "node_participant_id": item.node_participant_id,
            "task_id": item.task_id,
            "node_id": item.node_id,
            "employee_no": item.employee_no,
            "participant_role": item.participant_role,
        }

    @staticmethod
    def _extraction_dict(item: AIExtractionRecord) -> dict[str, Any]:
        return {
            "extraction_id": item.extraction_id,
            "input_id": item.input_id,
            "task_id": item.task_id,
            "extracted_json": item.extracted_json,
            "missing_fields": item.missing_fields,
            "low_confidence_fields": item.low_confidence_fields,
            "confirm_questions": item.confirm_questions,
            "confidence_score": item.confidence_score,
            "confirmed_at": item.confirmed_at,
        }

    @staticmethod
    def _status_log_dict(item: TaskStatusLog) -> dict[str, Any]:
        fields = (
            "status_log_id",
            "task_id",
            "from_status",
            "to_status",
            "action_type",
            "reason",
            "operator_employee_no",
            "target_employee_no",
            "task_version",
            "business_ref_type",
            "business_ref_id",
            "operation_source",
            "created_at",
        )
        return {field: getattr(item, field) for field in fields}

    @staticmethod
    def _completion_review_dict(
        item: TaskCompletionReview,
    ) -> dict[str, Any]:
        fields = (
            "completion_review_id",
            "task_id",
            "review_round",
            "submitted_by_employee_no",
            "completion_note",
            "deliverable_summary",
            "reviewer_employee_no",
            "review_status",
            "review_result",
            "reject_reason",
            "rework_node_id",
            "submitted_task_version",
            "reviewed_task_version",
            "submitted_at",
            "reviewed_at",
            "is_legacy_import",
        )
        return {field: getattr(item, field) for field in fields}
