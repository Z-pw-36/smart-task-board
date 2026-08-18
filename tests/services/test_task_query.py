from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import Task, TaskNode, TaskNodeParticipant, TaskParticipant, TaskStatusLog
from app.services.errors import BusinessValidationError, EntityNotFoundError, PermissionDeniedError
from app.services.task_query import TaskQueryService

NOW = datetime(2026, 8, 18, tzinfo=UTC)


def _service() -> tuple[TaskQueryService, MagicMock, Task, TaskNode]:
    session = MagicMock(spec=Session)
    service = TaskQueryService(session)
    task = Task(
        task_id=uuid4(),
        task_name="Task",
        creator_employee_no="CREATOR",
        main_assignee_employee_no="ASSIGNEE",
        report_to_employee_no="REPORTER",
        reviewer_employee_no="REVIEWER",
        status="in_progress",
        task_version=3,
        created_at=NOW,
        updated_at=NOW,
    )
    node = TaskNode(
        node_id=uuid4(),
        task_id=task.task_id,
        node_order=1,
        sort_weight=0,
        node_name="Node",
        owner_employee_no="OWNER",
        status="pending",
        progress_percent=0,
    )
    service._tasks = MagicMock()  # noqa: SLF001
    service._nodes = MagicMock()  # noqa: SLF001
    service._logs = MagicMock()  # noqa: SLF001
    service._extractions = MagicMock()  # noqa: SLF001
    service._tasks.get_by_id.return_value = task  # noqa: SLF001
    service._tasks.list_participants.return_value = [  # noqa: SLF001
        TaskParticipant(
            participant_id=uuid4(),
            task_id=task.task_id,
            employee_no="PARTICIPANT",
            participant_role="collaborator",
            is_primary=False,
        )
    ]
    service._nodes.list_nodes.return_value = [node]  # noqa: SLF001
    service._nodes.list_dependencies.return_value = []  # noqa: SLF001
    service._nodes.list_participants_by_task_id.return_value = [  # noqa: SLF001
        TaskNodeParticipant(
            node_participant_id=uuid4(),
            task_id=task.task_id,
            node_id=node.node_id,
            employee_no="NODE-PARTICIPANT",
            participant_role="collaborator",
        )
    ]
    service._nodes.get_node.return_value = node  # noqa: SLF001
    service._extractions.list_by_task_id.return_value = []  # noqa: SLF001
    return service, session, task, node


@pytest.mark.parametrize(
    "actor",
    [
        "CREATOR",
        "ASSIGNEE",
        "REPORTER",
        "REVIEWER",
        "PARTICIPANT",
        "OWNER",
        "NODE-PARTICIPANT",
    ],
)
def test_all_approved_relationships_can_read(actor: str) -> None:
    service, session, task, _ = _service()

    result = service.get_task_detail(task.task_id, actor)

    assert result["task_id"] == task.task_id
    assert task.task_version == 3
    session.commit.assert_not_called()
    session.flush.assert_not_called()


def test_unrelated_actor_and_missing_task_are_rejected() -> None:
    service, _, task, _ = _service()
    with pytest.raises(PermissionDeniedError):
        service.get_task_detail(task.task_id, "OUTSIDER")

    service._tasks.get_by_id.return_value = None  # noqa: SLF001
    with pytest.raises(EntityNotFoundError):
        service.get_task_detail(task.task_id, "CREATOR")


def test_node_must_belong_to_task() -> None:
    service, _, task, node = _service()
    node.task_id = uuid4()

    with pytest.raises(EntityNotFoundError):
        service.get_node(task.task_id, node.node_id, "CREATOR")


def test_status_logs_are_bounded_and_stably_projected() -> None:
    service, session, task, _ = _service()
    log = TaskStatusLog(
        status_log_id=uuid4(),
        task_id=task.task_id,
        from_status="draft",
        to_status="pending_confirmation",
        action_type="submitted_for_confirmation",
        operator_employee_no="CREATOR",
        task_version=2,
        operation_source="rest_api",
        created_at=NOW,
    )
    service._logs.list_by_task_id_paginated.return_value = [log]  # noqa: SLF001
    service._logs.count_by_task_id.return_value = 1  # noqa: SLF001

    result = service.list_status_logs(
        task.task_id,
        "CREATOR",
        limit=20,
        offset=0,
    )

    assert result["total"] == 1
    assert result["items"][0]["task_version"] == 2
    service._logs.list_by_task_id_paginated.assert_called_once_with(  # noqa: SLF001
        task.task_id,
        limit=20,
        offset=0,
    )
    session.commit.assert_not_called()

    with pytest.raises(BusinessValidationError):
        service.list_status_logs(task.task_id, "CREATOR", limit=101, offset=0)
