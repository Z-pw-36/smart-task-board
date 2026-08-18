from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from app.models import AIExtractionRecord, Department, Task, TaskNode, TaskParticipant, User
from app.services import (
    BusinessValidationError,
    CreateTaskDraftCommand,
    InvalidStateTransitionError,
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
    uow.task_status_logs.add.side_effect = lambda value: value
    return TaskWorkflowService(Mock(return_value=uow), clock=lambda: NOW), uow


def _last_log(uow: MagicMock):
    return uow.task_status_logs.add.call_args.args[0]


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


def test_submit_and_approve_completion_enforce_reviewer_and_terminal_state() -> None:
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

    service.submit_completion(task.task_id, "ASSIGNEE", 8, "unit-test")
    assert task.status == "pending_review"
    assert task.task_version == 9
    assert task.completed_at is None
    assert _last_log(uow).action_type == "completion_submitted"

    uow.reset_mock()
    uow.__enter__.return_value = uow
    uow.tasks.get_by_id_for_update.return_value = task
    uow.task_nodes.list_nodes.return_value = nodes
    uow.task_nodes.list_dependencies.return_value = []
    uow.task_status_logs.add.side_effect = lambda value: value
    with pytest.raises(PermissionDeniedError):
        service.approve_completion(task.task_id, "CREATOR", 9, "unit-test")
    assert task.task_version == 9
    uow.commit.assert_not_called()

    service.approve_completion(task.task_id, "REVIEWER", 9, "unit-test")
    assert task.status == "completed"
    assert task.task_version == 10
    assert task.completed_at == NOW
    assert _last_log(uow).action_type == "completion_approved"

    with pytest.raises(InvalidStateTransitionError):
        service.approve_completion(task.task_id, "REVIEWER", 10, "unit-test")


def test_creator_is_reviewer_when_explicit_reviewer_is_absent() -> None:
    task = _task(status="pending_review", reviewer=None, version=5)
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
    service, _ = _workflow_context(task, nodes=nodes)

    service.approve_completion(task.task_id, "CREATOR", 5, "unit-test")

    assert task.status == "completed"


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
        service.submit_completion(task.task_id, "ASSIGNEE", 4, "unit-test")

    assert (task.status, task.task_version) == ("in_progress", 4)
    uow.commit.assert_not_called()
