from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from app.models import Task, TaskNode, TaskNodeParticipant, TaskProgressReport
from app.services import (
    BusinessValidationError,
    PermissionDeniedError,
    ProgressReportService,
    SubmitProgressReportCommand,
)
from app.services.progress_report import task_report_period

NOW = datetime(2026, 8, 19, 2, 0, tzinfo=UTC)  # Wednesday 10:00 in Shanghai
ACCEPTED = datetime(2026, 8, 17, 1, 0, tzinfo=UTC)  # Monday 09:00 in Shanghai


def _context(*, node: TaskNode | None = None):
    task = Task(
        task_id=uuid4(),
        task_name="Task",
        creator_employee_no="CREATOR",
        main_assignee_employee_no="ASSIGNEE",
        status="in_progress",
        task_version=4,
        report_cycle="weekly:WED@09:00",
        accepted_at=ACCEPTED,
        created_at=ACCEPTED,
        updated_at=ACCEPTED,
    )
    if node is not None:
        node.task_id = task.task_id
    uow = MagicMock()
    uow.__enter__.return_value = uow
    uow.__exit__.return_value = False
    uow.tasks.get_by_id_for_update.return_value = task
    uow.task_nodes.get_node.return_value = node
    uow.progress_reports.add.side_effect = lambda value: value
    uow.progress_reports.has_root_task_report_for_period.return_value = False
    uow.task_status_logs.add.side_effect = lambda value: value
    service = ProgressReportService(Mock(return_value=uow), clock=lambda: NOW)
    return service, uow, task


def _command(task: Task, **overrides):
    values = {
        "task_id": task.task_id,
        "reporter_employee_no": "ASSIGNEE",
        "expected_task_version": 4,
        "operation_source": "unit-test",
        "progress_percent": 40,
        "report_content": "Made progress",
        **overrides,
    }
    return SubmitProgressReportCommand(**values)


def test_weekly_period_uses_first_boundary_strictly_after_acceptance() -> None:
    start, end = task_report_period(
        "weekly:MON@09:00",
        ACCEPTED,
        datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
    )

    assert start == ACCEPTED
    assert end == datetime(2026, 8, 24, 1, 0, tzinfo=UTC)


def test_task_report_is_append_only_versioned_and_periodized() -> None:
    service, uow, task = _context()

    report = service.submit(_command(task, actual_hours=Decimal("3.5")))

    assert report.task_version == 5
    assert report.node_id is None
    assert report.report_period_start == ACCEPTED
    assert report.report_period_end == datetime(2026, 8, 19, 1, 0, tzinfo=UTC)
    assert task.task_version == 5
    log = uow.task_status_logs.add.call_args.args[0]
    assert (log.action_type, log.business_ref_type, log.business_ref_id) == (
        "progress_report_submitted",
        "progress_report",
        report.progress_report_id,
    )
    uow.commit.assert_called_once_with()


def test_task_report_rejects_duplicate_period_and_non_assignee() -> None:
    service, uow, task = _context()
    uow.progress_reports.has_root_task_report_for_period.return_value = True

    with pytest.raises(BusinessValidationError, match="already fulfills"):
        service.submit(_command(task))
    with pytest.raises(PermissionDeniedError):
        service.submit(_command(task, reporter_employee_no="OUTSIDER"))

    assert task.task_version == 4
    uow.commit.assert_not_called()


def test_node_owner_and_collaborator_can_report_without_fulfilling_task_period() -> None:
    node = TaskNode(
        node_id=uuid4(),
        task_id=uuid4(),
        node_order=1,
        node_name="Node",
        owner_employee_no="OWNER",
        status="in_progress",
        progress_percent=20,
    )
    service, uow, task = _context(node=node)

    owner_report = service.submit(
        _command(task, node_id=node.node_id, reporter_employee_no="OWNER")
    )
    assert (owner_report.report_period_start, owner_report.report_period_end) == (
        None,
        None,
    )

    task.task_version = 5
    participant = TaskNodeParticipant(
        task_id=task.task_id,
        node_id=node.node_id,
        employee_no="COLLAB",
        participant_role="collaborator",
    )
    uow.task_nodes.find_participant.side_effect = lambda *args: (
        participant if args[-1] == "collaborator" else None
    )
    collaborator_report = service.submit(
        _command(
            task,
            expected_task_version=5,
            node_id=node.node_id,
            reporter_employee_no="COLLAB",
        )
    )
    assert collaborator_report.node_id == node.node_id


def test_correction_targets_root_and_never_fulfills_another_period() -> None:
    service, uow, task = _context()
    root = TaskProgressReport(
        progress_report_id=uuid4(),
        task_id=task.task_id,
        reporter_employee_no="ASSIGNEE",
        progress_percent=20,
        report_content="Root",
        task_version=2,
        operation_source="unit-test",
        created_at=ACCEPTED,
    )
    correction = TaskProgressReport(
        progress_report_id=uuid4(),
        task_id=task.task_id,
        reporter_employee_no="ASSIGNEE",
        progress_percent=30,
        report_content="Correction",
        corrects_report_id=root.progress_report_id,
        task_version=3,
        operation_source="unit-test",
        created_at=ACCEPTED,
    )
    uow.progress_reports.get_by_task_and_id.side_effect = lambda _task_id, report_id: {
        root.progress_report_id: root,
        correction.progress_report_id: correction,
    }.get(report_id)

    result = service.submit(
        _command(task, corrects_report_id=correction.progress_report_id)
    )

    assert result.corrects_report_id == root.progress_report_id
    assert (result.report_period_start, result.report_period_end) == (None, None)
    assert uow.task_status_logs.add.call_args.args[0].action_type == (
        "progress_report_corrected"
    )


def test_correction_requires_same_reporter_and_node_scope() -> None:
    node = TaskNode(
        node_id=uuid4(),
        task_id=uuid4(),
        node_order=1,
        node_name="Node",
        owner_employee_no="ASSIGNEE",
    )
    service, uow, task = _context(node=node)
    root = TaskProgressReport(
        progress_report_id=uuid4(),
        task_id=task.task_id,
        reporter_employee_no="OTHER",
        progress_percent=20,
        report_content="Root",
        task_version=2,
        operation_source="unit-test",
    )
    uow.progress_reports.get_by_task_and_id.return_value = root

    with pytest.raises(PermissionDeniedError):
        service.submit(
            _command(
                task,
                node_id=node.node_id,
                corrects_report_id=root.progress_report_id,
            )
        )


@pytest.mark.parametrize(
    ("progress", "hours", "message"),
    [(-1, None, "progress_percent"), (101, None, "progress_percent"), (20, -1, "actual_hours")],
)
def test_report_numeric_validation(progress, hours, message) -> None:
    service, _, task = _context()
    with pytest.raises(BusinessValidationError, match=message):
        service.submit(
            _command(
                task,
                progress_percent=progress,
                actual_hours=None if hours is None else Decimal(hours),
            )
        )
