from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    CreateTaskRequest,
    ReturnTaskRequest,
    TaskActionRequest,
    TaskActionResponse,
    TaskNodeResponse,
    UpdateNodeProgressRequest,
)


def _valid_request() -> dict[str, object]:
    first, second = uuid4(), uuid4()
    return {
        "task_name": "Task",
        "start_time": "2026-08-18T08:00:00+08:00",
        "deadline": "2026-08-19T08:00:00+08:00",
        "estimated_hours": "3.50",
        "nodes": [
            {"node_id": str(first), "node_order": 1, "node_name": "First"},
            {"node_id": str(second), "node_order": 2, "node_name": "Second"},
        ],
        "dependencies": [
            {
                "predecessor_node_id": str(first),
                "successor_node_id": str(second),
            }
        ],
        "node_participants": [
            {
                "node_id": str(first),
                "employee_no": "E001",
                "participant_role": "owner",
            }
        ],
    }


def test_create_request_accepts_real_fields_and_decimal() -> None:
    request = CreateTaskRequest.model_validate(_valid_request())

    assert request.task_name == "Task"
    assert request.estimated_hours == Decimal("3.50")
    assert request.start_time is not None and request.start_time.tzinfo is not None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("creator_employee_no", "E-CREATOR"),
        ("operation_source", "client"),
        ("status", "draft"),
        ("unexpected", "value"),
    ],
)
def test_create_request_forbids_server_owned_and_extra_fields(
    field: str,
    value: str,
) -> None:
    payload = _valid_request()
    payload[field] = value

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CreateTaskRequest.model_validate(payload)


def test_create_request_requires_name_and_valid_uuid() -> None:
    with pytest.raises(ValidationError):
        CreateTaskRequest.model_validate({})
    with pytest.raises(ValidationError):
        CreateTaskRequest.model_validate(
            {
                "task_name": "Task",
                "nodes": [
                    {
                        "node_id": "not-uuid",
                        "node_order": 1,
                        "node_name": "Node",
                    }
                ],
            }
        )


def test_create_request_rejects_naive_datetime_and_bad_references() -> None:
    payload = _valid_request()
    payload["start_time"] = "2026-08-18T08:00:00"
    with pytest.raises(ValidationError, match="timezone"):
        CreateTaskRequest.model_validate(payload)

    payload = _valid_request()
    payload["dependencies"] = [
        {
            "predecessor_node_id": str(payload["nodes"][0]["node_id"]),  # type: ignore[index]
            "successor_node_id": str(uuid4()),
        }
    ]
    with pytest.raises(ValidationError, match="dependency"):
        CreateTaskRequest.model_validate(payload)

    payload = _valid_request()
    payload["node_participants"] = [
        {
            "node_id": str(uuid4()),
            "employee_no": "E001",
            "participant_role": "owner",
        }
    ]
    with pytest.raises(ValidationError, match="node participant"):
        CreateTaskRequest.model_validate(payload)


def test_create_request_rejects_duplicate_nodes() -> None:
    node_id = uuid4()
    with pytest.raises(ValidationError, match="unique"):
        CreateTaskRequest.model_validate(
            {
                "task_name": "Task",
                "nodes": [
                    {"node_id": node_id, "node_order": 1, "node_name": "One"},
                    {"node_id": node_id, "node_order": 2, "node_name": "Two"},
                ],
            }
        )


def test_action_request_boundaries_and_blank_reason() -> None:
    with pytest.raises(ValidationError):
        TaskActionRequest(expected_task_version=0)
    with pytest.raises(ValidationError):
        ReturnTaskRequest(expected_task_version=1, reason="  ")
    with pytest.raises(ValidationError):
        UpdateNodeProgressRequest(expected_task_version=1, progress_percent=101)
    with pytest.raises(ValidationError):
        UpdateNodeProgressRequest(
            expected_task_version=1,
            progress_percent=50,
            actual_hours=Decimal("-1"),
        )


def test_status_literal_and_decimal_json_serialization() -> None:
    response = TaskActionResponse(
        task_id=uuid4(),
        status="draft",
        task_version=1,
        updated_at=datetime(2026, 8, 18, tzinfo=UTC),
    )
    assert response.model_dump(mode="json")["updated_at"].endswith("Z")

    node = TaskNodeResponse(
        node_id=uuid4(),
        task_id=uuid4(),
        node_order=1,
        sort_weight=0,
        node_name="Node",
        action_detail=None,
        tools_or_materials=None,
        owner_employee_no=None,
        planned_start_time=None,
        planned_deadline=None,
        estimated_hours=Decimal("4.25"),
        actual_hours=Decimal("1.50"),
        deliverable=None,
        acceptance_criteria=None,
        progress_percent=50,
        status="in_progress",
        completed_at=None,
    )
    assert node.model_dump(mode="json")["actual_hours"] == "1.50"

    with pytest.raises(ValidationError):
        TaskActionResponse(
            task_id=uuid4(),
            status="unknown",  # type: ignore[arg-type]
            task_version=1,
            updated_at=datetime(2026, 8, 18, tzinfo=UTC),
        )
