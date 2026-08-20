from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.unit_of_work import UnitOfWork
from app.models import (
    AIExtractionRecord,
    Department,
    Task,
    TaskCompletionReview,
    TaskNode,
    TaskParticipant,
    User,
)
from app.services import (
    BusinessValidationError,
    CreateTaskDraftCommand,
    EntityNotFoundError,
    InvalidStateTransitionError,
    OpenTaskIssueConflictError,
    PermissionDeniedError,
    TaskNodeDependencyDraft,
    TaskNodeDraft,
    TaskNodeParticipantDraft,
    TaskParticipantDraft,
    TaskVersionConflictError,
    TaskWorkflowService,
)
from app.services.task_workflow import (
    PARTICIPANT_CONFIRM_ACCEPTED,
    PARTICIPANT_CONFIRM_PENDING,
    PARTICIPANT_CONFIRM_RETURNED,
)

NOW = datetime(2026, 8, 18, 8, 0, tzinfo=UTC)


def _task(
    *,
    status: str,
    creator: str = "CREATOR",
    assignee: str | None = "ASSIGNEE",
    reviewer: str | None = "REVIEWER",
    version: int = 1,
) -> Task:
    return Task(
        task_id=uuid4(),
        task_name="Workflow task",
        creator_employee_no=creator,
        main_assignee_employee_no=assignee,
        reviewer_employee_no=reviewer,
        status=status,
        task_version=version,
        created_at=NOW,
        updated_at=NOW,
    )


def _participant(task: Task) -> TaskParticipant:
    return TaskParticipant(
        task_id=task.task_id,
        employee_no=task.main_assignee_employee_no or "ASSIGNEE",
        participant_role="assignee",
        is_primary=True,
    )


def _workflow_context(
    task: Task,
    *,
    nodes: list[TaskNode] | None = None,
    participant: TaskParticipant | None = None,
) -> tuple[TaskWorkflowService, MagicMock]:
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.__exit__.return_value = False
    uow.tasks.get_by_id_for_update.return_value = task
    uow.tasks.find_participant.return_value = participant or _participant(task)
    uow.task_nodes.list_nodes.return_value = nodes or []
    uow.task_nodes.list_dependencies.return_value = []
    uow.task_issues.has_non_closed.return_value = False
    uow.task_completion_reviews.add.side_effect = lambda value: value
    uow.task_completion_reviews.next_round.return_value = 1
    uow.task_completion_reviews.get_latest_rejected.return_value = None
    uow.task_status_logs.has_action_for_business_ref.return_value = False
    uow.task_status_logs.add.side_effect = lambda value: value
    return TaskWorkflowService(Mock(return_value=uow), clock=lambda: NOW), uow


def _last_log(uow: MagicMock):
    return uow.task_status_logs.add.call_args.args[0]


def _completion_review(
    task: Task,
    *,
    review_status: str = "submitted",
    review_round: int = 1,
    reviewer: str = "REVIEWER",
    rework_node_id=None,
) -> TaskCompletionReview:
    submitted_version = (
        task.task_version
        if review_status == "submitted"
        else max(1, task.task_version - 1)
    )
    review = TaskCompletionReview(
        completion_review_id=uuid4(),
        task_id=task.task_id,
        review_round=review_round,
        submitted_by_employee_no="ASSIGNEE",
        completion_note="Completion note",
        deliverable_summary="Deliverable summary",
        reviewer_employee_no=reviewer,
        review_status=review_status,
        submitted_task_version=submitted_version,
        submitted_at=NOW,
        is_legacy_import=False,
    )
    if review_status in {"approved", "rejected"}:
        review.review_result = review_status
        review.reviewed_at = NOW
        review.reviewed_task_version = max(
            submitted_version + 1,
            task.task_version,
        )
    if review_status == "rejected":
        review.reject_reason = "Needs rework"
        review.rework_node_id = rework_node_id
    return review


def test_create_task_draft_builds_complete_aggregate_and_log() -> None:
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.__exit__.return_value = False
    uow.users.get_by_employee_no.side_effect = lambda employee_no: User(
        employee_no=employee_no,
        name=employee_no,
        role_type="employee",
        status="active",
    )
    department_id = uuid4()
    uow.departments.get_by_id.return_value = Department(
        department_id=department_id,
        department_name="Department",
        department_type="team",
        department_path="/department",
        status="active",
    )
    extraction = AIExtractionRecord(
        extraction_id=uuid4(),
        input_id=uuid4(),
        extracted_json={},
        missing_fields=[],
        low_confidence_fields=[],
        confirm_questions=[],
    )
    uow.ai_extraction_records.get_by_id.return_value = extraction
    uow.task_status_logs.add.side_effect = lambda value: value
    first, second = uuid4(), uuid4()
    command = CreateTaskDraftCommand(
        task_name="  New task  ",
        creator_employee_no="CREATOR",
        main_assignee_employee_no="ASSIGNEE",
        reviewer_employee_no="REVIEWER",
        department_id=department_id,
        operation_source="unit-test",
        estimated_hours=Decimal("2"),
        participants=(TaskParticipantDraft("COLLAB", "collaborator"),),
        nodes=(
            TaskNodeDraft(first, 1, "First", owner_employee_no="ASSIGNEE"),
            TaskNodeDraft(second, 2, "Second"),
        ),
        dependencies=(TaskNodeDependencyDraft(first, second),),
        node_participants=(
            TaskNodeParticipantDraft(first, "COLLAB", "collaborator"),
        ),
        extraction_record_ids=(extraction.extraction_id,),
    )
    service = TaskWorkflowService(Mock(return_value=uow), clock=lambda: NOW)

    task = service.create_task_draft(command)

    assert task.status == "draft"
    assert task.task_version == 1
    assert task.task_name == "New task"
    assert task.task_no is None
    assert extraction.task_id == task.task_id
    assert uow.tasks.add_participant.call_count == 2
    primary = uow.tasks.add_participant.call_args_list[0].args[0]
    assert (primary.employee_no, primary.participant_role, primary.is_primary) == (
        "ASSIGNEE",
        "assignee",
        True,
    )
    assert uow.task_nodes.add_node.call_count == 2
    assert uow.task_nodes.add_dependency.call_count == 1
    assert uow.task_nodes.add_participant.call_count == 1
    log = _last_log(uow)
    assert (log.from_status, log.to_status, log.action_type, log.task_version) == (
        None,
        "draft",
        "task_created",
        1,
    )
    assert log.created_at == NOW
    uow.commit.assert_called_once_with()


def test_create_task_draft_rejects_cycle_before_opening_transaction() -> None:
    first, second = uuid4(), uuid4()
    factory = Mock()
    service = TaskWorkflowService(factory, clock=lambda: NOW)
    command = CreateTaskDraftCommand(
        task_name="Cycle",
        creator_employee_no="CREATOR",
        operation_source="unit-test",
        nodes=(TaskNodeDraft(first, 1, "First"), TaskNodeDraft(second, 2, "Second")),
        dependencies=(
            TaskNodeDependencyDraft(first, second),
            TaskNodeDependencyDraft(second, first),
        ),
    )

    with pytest.raises(Exception, match="cycle"):
        service.create_task_draft(command)

    factory.assert_not_called()


def test_submit_for_confirmation_increments_once_and_logs() -> None:
    task = _task(status="draft", version=4)
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Node",
        status="pending",
        progress_percent=0,
    )
    service, uow = _workflow_context(task, nodes=[node])

    result = service.submit_for_confirmation(
        task.task_id,
        "CREATOR",
        4,
        "unit-test",
    )

    assert result.status == "pending_confirmation"
    assert result.task_version == 5
    log = _last_log(uow)
    assert (log.action_type, log.from_status, log.to_status, log.task_version) == (
        "submitted_for_confirmation",
        "draft",
        "pending_confirmation",
        5,
    )
    uow.commit.assert_called_once_with()


def test_confirm_send_accept_updates_projection_and_times() -> None:
    task = _task(status="pending_confirmation", version=2)
    participant = _participant(task)
    service, uow = _workflow_context(task, participant=participant)

    service.confirm_and_send(task.task_id, "CREATOR", 2, "unit-test")

    assert task.status == "pending_acceptance"
    assert task.task_version == 3
    assert task.confirmed_at == task.sent_at == NOW
    assert task.accepted_at is None
    assert participant.confirm_status == PARTICIPANT_CONFIRM_PENDING
    assert _last_log(uow).action_type == "confirmed_and_sent"

    uow.reset_mock()
    uow.__enter__.return_value = uow
    uow.tasks.get_by_id_for_update.return_value = task
    uow.tasks.find_participant.return_value = participant
    uow.task_status_logs.add.side_effect = lambda value: value
    service.accept_task(task.task_id, "ASSIGNEE", 3, "unit-test")

    assert task.status == "in_progress"
    assert task.task_version == 4
    assert task.accepted_at == NOW
    assert participant.confirm_status == PARTICIPANT_CONFIRM_ACCEPTED
    assert participant.confirmed_at == NOW
    assert _last_log(uow).action_type == "task_accepted"


def test_self_assigned_confirmation_goes_directly_to_in_progress() -> None:
    task = _task(
        status="pending_confirmation",
        creator="OWNER",
        assignee="OWNER",
        version=2,
    )
    participant = _participant(task)
    service, uow = _workflow_context(task, participant=participant)

    service.confirm_self_assigned(task.task_id, "OWNER", 2, "unit-test")

    assert task.status == "in_progress"
    assert task.task_version == 3
    assert task.confirmed_at == task.sent_at == task.accepted_at == NOW
    assert participant.confirm_status == PARTICIPANT_CONFIRM_ACCEPTED
    assert _last_log(uow).action_type == "self_assigned_confirmed"


def test_return_and_resend_require_reason_and_update_projection() -> None:
    task = _task(status="pending_acceptance", version=3)
    participant = _participant(task)
    service, uow = _workflow_context(task, participant=participant)

    with pytest.raises(BusinessValidationError, match="reason"):
        service.return_task(task.task_id, "ASSIGNEE", 3, "unit-test", "  ")

    service.return_task(task.task_id, "ASSIGNEE", 3, "unit-test", " revise ")
    assert task.status == "returned"
    assert task.task_version == 4
    assert participant.confirm_status == PARTICIPANT_CONFIRM_RETURNED
    assert _last_log(uow).reason == "revise"

    uow.reset_mock()
    uow.__enter__.return_value = uow
    uow.tasks.get_by_id_for_update.return_value = task
    uow.tasks.find_participant.return_value = participant
    uow.task_status_logs.add.side_effect = lambda value: value
    service.resend_task(task.task_id, "CREATOR", 4, "unit-test")
    assert task.status == "pending_acceptance"
    assert task.task_version == 5
    assert participant.confirm_status == PARTICIPANT_CONFIRM_PENDING
    assert _last_log(uow).action_type == "task_resent"


def test_submit_completion_creates_snapshot_round_and_referenced_log() -> None:
    task = _task(status="in_progress", version=8)
    nodes = [
        TaskNode(
            node_id=uuid4(),
            task_id=task.task_id,
            node_order=1,
            node_name="Done",
            status="completed",
            progress_percent=100,
        )
    ]
    service, uow = _workflow_context(task, nodes=nodes)
    uow.task_completion_reviews.next_round.return_value = 3

    result_task, review = service.submit_completion(
        task.task_id,
        "ASSIGNEE",
        8,
        "unit-test",
        "  Ready for review  ",
        "  Release package  ",
    )

    assert result_task is task
    assert (task.status, task.task_version, task.completed_at) == (
        "pending_review",
        9,
        None,
    )
    assert (
        review.task_id,
        review.review_round,
        review.submitted_by_employee_no,
        review.reviewer_employee_no,
    ) == (task.task_id, 3, "ASSIGNEE", "REVIEWER")
    assert (review.completion_note, review.deliverable_summary) == (
        "Ready for review",
        "Release package",
    )
    assert (
        review.review_status,
        review.submitted_task_version,
        review.submitted_at,
        review.is_legacy_import,
    ) == ("submitted", 9, NOW, False)
    uow.task_completion_reviews.add.assert_called_once_with(review)
    log = _last_log(uow)
    assert (
        log.action_type,
        log.from_status,
        log.to_status,
        log.task_version,
        log.target_employee_no,
    ) == (
        "completion_submitted",
        "in_progress",
        "pending_review",
        9,
        "REVIEWER",
    )
    assert (log.business_ref_type, log.business_ref_id) == (
        "completion_review",
        review.completion_review_id,
    )
    uow.commit.assert_called_once_with()


def test_approve_completion_uses_snapshot_reviewer_and_decides_once() -> None:
    task = _task(status="pending_review", reviewer="CHANGED", version=9)
    nodes = [
        TaskNode(
            node_id=uuid4(),
            task_id=task.task_id,
            node_order=1,
            node_name="Done",
            status="completed",
            progress_percent=100,
        )
    ]
    review = _completion_review(task, reviewer="SNAPSHOT")
    service, uow = _workflow_context(task, nodes=nodes)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review

    with pytest.raises(PermissionDeniedError):
        service.approve_completion(
            task.task_id,
            "CHANGED",
            9,
            "unit-test",
            review.completion_review_id,
        )
    assert (task.status, task.task_version, review.review_status) == (
        "pending_review",
        9,
        "submitted",
    )
    uow.commit.assert_not_called()

    result_task, result_review = service.approve_completion(
        task.task_id,
        "SNAPSHOT",
        9,
        "unit-test",
        review.completion_review_id,
    )
    assert (result_task, result_review) == (task, review)
    assert (task.status, task.task_version, task.completed_at) == (
        "completed",
        10,
        NOW,
    )
    assert (
        review.review_status,
        review.review_result,
        review.reviewed_at,
        review.reviewed_task_version,
    ) == ("approved", "approved", NOW, 10)
    log = _last_log(uow)
    assert (log.action_type, log.task_version) == ("completion_approved", 10)
    assert (log.business_ref_type, log.business_ref_id) == (
        "completion_review",
        review.completion_review_id,
    )

    with pytest.raises(InvalidStateTransitionError):
        service.approve_completion(
            task.task_id,
            "SNAPSHOT",
            10,
            "unit-test",
            review.completion_review_id,
        )


def test_creator_is_snapshotted_when_explicit_reviewer_is_absent() -> None:
    task = _task(status="in_progress", reviewer=None, version=5)
    nodes = [
        TaskNode(
            node_id=uuid4(),
            task_id=task.task_id,
            node_order=1,
            node_name="Done",
            status="completed",
            progress_percent=100,
        )
    ]
    service, uow = _workflow_context(task, nodes=nodes)

    _, review = service.submit_completion(
        task.task_id,
        "ASSIGNEE",
        5,
        "unit-test",
        "Done",
        "Artifact",
    )

    assert review.reviewer_employee_no == "CREATOR"
    assert _last_log(uow).target_employee_no == "CREATOR"


def test_version_and_permission_failures_do_not_commit_or_modify_task() -> None:
    task = _task(status="draft", version=7)
    service, uow = _workflow_context(task)

    with pytest.raises(TaskVersionConflictError):
        service.submit_for_confirmation(task.task_id, "CREATOR", 6, "unit-test")
    with pytest.raises(PermissionDeniedError):
        service.submit_for_confirmation(task.task_id, "OUTSIDER", 7, "unit-test")

    assert (task.status, task.task_version) == ("draft", 7)
    uow.commit.assert_not_called()


def test_completion_requires_all_nodes_completed() -> None:
    task = _task(status="in_progress", version=4)
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Open",
        status="in_progress",
        progress_percent=50,
    )
    service, uow = _workflow_context(task, nodes=[node])

    with pytest.raises(BusinessValidationError, match="completed"):
        service.submit_completion(
            task.task_id,
            "ASSIGNEE",
            4,
            "unit-test",
            "Done",
            "Artifact",
        )

    assert (task.status, task.task_version) == ("in_progress", 4)
    uow.commit.assert_not_called()


def test_completion_requires_every_issue_to_be_closed() -> None:
    task = _task(status="in_progress", version=4)
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Done",
        status="completed",
        progress_percent=100,
    )
    service, uow = _workflow_context(task, nodes=[node])
    uow.task_issues.has_non_closed.return_value = True

    with pytest.raises(OpenTaskIssueConflictError):
        service.submit_completion(
            task.task_id,
            "ASSIGNEE",
            4,
            "unit-test",
            "Done",
            "Artifact",
        )

    assert (task.status, task.task_version) == ("in_progress", 4)
    uow.commit.assert_not_called()


@pytest.mark.parametrize(
    ("completion_note", "deliverable_summary", "field_name"),
    [
        ("  ", "Artifact", "completion_note"),
        ("Done", "\t", "deliverable_summary"),
    ],
)
def test_submit_completion_rejects_blank_user_content_before_transaction(
    completion_note: str,
    deliverable_summary: str,
    field_name: str,
) -> None:
    factory = Mock()
    service = TaskWorkflowService(factory, clock=lambda: NOW)

    with pytest.raises(BusinessValidationError, match=field_name):
        service.submit_completion(
            uuid4(),
            "ASSIGNEE",
            1,
            "unit-test",
            completion_note,
            deliverable_summary,
        )

    factory.assert_not_called()


def test_submit_completion_requires_main_assignee_and_exact_version() -> None:
    task = _task(status="in_progress", version=6)
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Done",
        status="completed",
        progress_percent=100,
    )
    service, uow = _workflow_context(task, nodes=[node])

    with pytest.raises(TaskVersionConflictError):
        service.submit_completion(
            task.task_id,
            "ASSIGNEE",
            5,
            "unit-test",
            "Done",
            "Artifact",
        )
    with pytest.raises(PermissionDeniedError):
        service.submit_completion(
            task.task_id,
            "CREATOR",
            6,
            "unit-test",
            "Done",
            "Artifact",
        )

    assert (task.status, task.task_version) == ("in_progress", 6)
    uow.task_completion_reviews.add.assert_not_called()
    uow.commit.assert_not_called()


def test_completed_status_without_100_percent_cannot_be_submitted_or_approved() -> None:
    task = _task(status="in_progress", version=6)
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Inconsistent",
        status="completed",
        progress_percent=99,
    )
    service, uow = _workflow_context(task, nodes=[node])

    with pytest.raises(BusinessValidationError, match="100 percent"):
        service.submit_completion(
            task.task_id,
            "ASSIGNEE",
            6,
            "unit-test",
            "Done",
            "Artifact",
        )

    task.status = "pending_review"
    review = _completion_review(task)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    with pytest.raises(BusinessValidationError, match="100 percent"):
        service.approve_completion(
            task.task_id,
            "REVIEWER",
            6,
            "unit-test",
            review.completion_review_id,
        )

    assert (task.status, task.task_version, review.review_status) == (
        "pending_review",
        6,
        "submitted",
    )
    uow.commit.assert_not_called()


def test_targeted_rework_requires_explicit_reopen_after_rejection_version() -> None:
    task = _task(status="in_progress", version=12)
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Reworked",
        status="completed",
        progress_percent=100,
    )
    rejected = _completion_review(
        task,
        review_status="rejected",
        rework_node_id=node.node_id,
    )
    rejected.reviewed_task_version = 10
    service, uow = _workflow_context(task, nodes=[node])
    uow.task_completion_reviews.get_latest_rejected.return_value = rejected
    uow.task_completion_reviews.next_round.return_value = 2

    with pytest.raises(InvalidStateTransitionError, match="explicitly reopened"):
        service.submit_completion(
            task.task_id,
            "ASSIGNEE",
            12,
            "unit-test",
            "Reworked",
            "Updated artifact",
        )
    uow.task_status_logs.has_action_for_business_ref.assert_called_once_with(
        task.task_id,
        "node_reopened",
        "completion_review",
        rejected.completion_review_id,
        after_task_version=10,
    )
    assert (task.status, task.task_version) == ("in_progress", 12)
    uow.commit.assert_not_called()

    uow.task_status_logs.has_action_for_business_ref.return_value = True
    _, second_round = service.submit_completion(
        task.task_id,
        "ASSIGNEE",
        12,
        "unit-test",
        "Reworked",
        "Updated artifact",
    )
    assert (second_round.review_round, second_round.submitted_task_version) == (
        2,
        13,
    )


def test_overall_rework_can_be_resubmitted_without_node_reopen() -> None:
    task = _task(status="in_progress", version=14)
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Done",
        status="completed",
        progress_percent=100,
    )
    rejected = _completion_review(task, review_status="rejected", review_round=2)
    service, uow = _workflow_context(task, nodes=[node])
    uow.task_completion_reviews.get_latest_rejected.return_value = rejected
    uow.task_completion_reviews.next_round.return_value = 3

    _, review = service.submit_completion(
        task.task_id,
        "ASSIGNEE",
        14,
        "unit-test",
        "Overall revision",
        "Third artifact",
    )

    assert (review.review_round, task.task_version) == (3, 15)
    uow.task_status_logs.has_action_for_business_ref.assert_not_called()


def test_reject_completion_records_decision_without_mutating_rework_node() -> None:
    task = _task(status="pending_review", reviewer="CHANGED", version=9)
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Needs changes",
        status="completed",
        progress_percent=100,
        actual_hours=Decimal("4.5"),
        completed_at=NOW,
    )
    review = _completion_review(task, reviewer="SNAPSHOT")
    service, uow = _workflow_context(task, nodes=[node])
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    uow.task_nodes.get_node.return_value = node
    original_node_projection = (
        node.status,
        node.progress_percent,
        node.actual_hours,
        node.completed_at,
    )

    result_task, result_review = service.reject_completion(
        task.task_id,
        "SNAPSHOT",
        9,
        "unit-test",
        review.completion_review_id,
        "  Update the evidence  ",
        node.node_id,
    )

    assert (result_task, result_review) == (task, review)
    assert (task.status, task.task_version, task.completed_at) == (
        "in_progress",
        10,
        None,
    )
    assert (
        review.review_status,
        review.review_result,
        review.reject_reason,
        review.rework_node_id,
        review.reviewed_at,
        review.reviewed_task_version,
    ) == (
        "rejected",
        "rejected",
        "Update the evidence",
        node.node_id,
        NOW,
        10,
    )
    assert (
        node.status,
        node.progress_percent,
        node.actual_hours,
        node.completed_at,
    ) == original_node_projection
    log = _last_log(uow)
    assert (
        log.action_type,
        log.reason,
        log.target_employee_no,
        log.task_version,
    ) == (
        "completion_rejected",
        "Update the evidence",
        "ASSIGNEE",
        10,
    )
    assert (log.business_ref_type, log.business_ref_id) == (
        "completion_review",
        review.completion_review_id,
    )


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_terminal_review_cannot_be_decided_again(decision: str) -> None:
    task = _task(status="pending_review", version=11)
    review = _completion_review(task, review_status="rejected")
    service, uow = _workflow_context(task)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review

    with pytest.raises(InvalidStateTransitionError, match="current submitted"):
        if decision == "approve":
            service.approve_completion(
                task.task_id,
                "REVIEWER",
                11,
                "unit-test",
                review.completion_review_id,
            )
        else:
            service.reject_completion(
                task.task_id,
                "REVIEWER",
                11,
                "unit-test",
                review.completion_review_id,
                "Again",
            )

    assert (task.status, task.task_version, review.review_status) == (
        "pending_review",
        11,
        "rejected",
    )
    uow.commit.assert_not_called()


def test_old_submitted_review_version_is_not_the_current_round() -> None:
    task = _task(status="pending_review", version=11)
    review = _completion_review(task)
    review.submitted_task_version = 9
    service, uow = _workflow_context(task)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review

    with pytest.raises(InvalidStateTransitionError, match="current submitted"):
        service.reject_completion(
            task.task_id,
            "REVIEWER",
            11,
            "unit-test",
            review.completion_review_id,
            "Stale round",
        )

    assert (task.status, task.task_version, review.review_status) == (
        "pending_review",
        11,
        "submitted",
    )
    uow.commit.assert_not_called()


def test_review_and_rework_node_are_task_scoped_and_fail_without_mutation() -> None:
    task = _task(status="pending_review", version=9)
    review = _completion_review(task)
    service, uow = _workflow_context(task)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = None

    with pytest.raises(EntityNotFoundError, match="completion review"):
        service.approve_completion(
            task.task_id,
            "REVIEWER",
            9,
            "unit-test",
            review.completion_review_id,
        )
    uow.task_completion_reviews.get_by_task_and_id_for_update.assert_called_with(
        task.task_id,
        review.completion_review_id,
    )

    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    other_task_node = TaskNode(
        node_id=uuid4(),
        task_id=uuid4(),
        node_order=1,
        node_name="Other task",
        status="completed",
        progress_percent=100,
    )
    uow.task_nodes.get_node.return_value = other_task_node
    with pytest.raises(BusinessValidationError, match="does not belong"):
        service.reject_completion(
            task.task_id,
            "REVIEWER",
            9,
            "unit-test",
            review.completion_review_id,
            "Rework",
            other_task_node.node_id,
        )

    assert (task.status, task.task_version, review.review_status) == (
        "pending_review",
        9,
        "submitted",
    )
    uow.commit.assert_not_called()
    assert uow.__exit__.called


def test_reject_requires_reason_snapshot_reviewer_and_completed_rework_node() -> None:
    factory = Mock()
    service = TaskWorkflowService(factory, clock=lambda: NOW)
    with pytest.raises(BusinessValidationError, match="reject_reason"):
        service.reject_completion(
            uuid4(),
            "REVIEWER",
            1,
            "unit-test",
            uuid4(),
            "  ",
        )
    factory.assert_not_called()

    task = _task(status="pending_review", reviewer="CHANGED", version=9)
    review = _completion_review(task, reviewer="SNAPSHOT")
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Open",
        status="in_progress",
        progress_percent=80,
    )
    service, uow = _workflow_context(task)
    uow.task_completion_reviews.get_by_task_and_id_for_update.return_value = review
    uow.task_nodes.get_node.return_value = node

    with pytest.raises(PermissionDeniedError):
        service.reject_completion(
            task.task_id,
            "CHANGED",
            9,
            "unit-test",
            review.completion_review_id,
            "Rework",
            node.node_id,
        )
    with pytest.raises(InvalidStateTransitionError, match="completed"):
        service.reject_completion(
            task.task_id,
            "SNAPSHOT",
            9,
            "unit-test",
            review.completion_review_id,
            "Rework",
            node.node_id,
        )

    assert (task.status, task.task_version, review.review_status) == (
        "pending_review",
        9,
        "submitted",
    )
    uow.commit.assert_not_called()


def test_submit_completion_commit_failure_rolls_back_the_unit_of_work() -> None:
    task = _task(status="in_progress", version=4)
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        node_name="Done",
        status="completed",
        progress_percent=100,
    )
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    nodes_result = MagicMock()
    nodes_result.scalars.return_value.all.return_value = [node]
    dependencies_result = MagicMock()
    dependencies_result.scalars.return_value.all.return_value = []
    issues_result = MagicMock()
    issues_result.scalar_one.return_value = False
    rejected_result = MagicMock()
    rejected_result.scalar_one_or_none.return_value = None
    round_result = MagicMock()
    round_result.scalar_one.return_value = 0
    session = MagicMock(spec=Session)
    session.execute.side_effect = [
        task_result,
        nodes_result,
        dependencies_result,
        issues_result,
        rejected_result,
        round_result,
    ]
    session.commit.side_effect = RuntimeError("database commit failed")
    service = TaskWorkflowService(
        lambda: UnitOfWork(lambda: session),
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeError, match="database commit failed"):
        service.submit_completion(
            task.task_id,
            "ASSIGNEE",
            4,
            "unit-test",
            "Done",
            "Artifact",
        )

    assert session.add.call_count == 2
    assert session.flush.call_count == 2
    session.commit.assert_called_once_with()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
