from datetime import timedelta

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Uuid,
    inspect,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.models import Task, TaskChangeRequest, User

FIELDS = {
    "change_request_id",
    "task_id",
    "requester_employee_no",
    "patch_json",
    "reason",
    "before_snapshot",
    "after_snapshot",
    "status",
    "requester_task_version",
    "base_task_version",
    "decision_by_employee_no",
    "decision_at",
    "decision_comment",
    "cancelled_by_employee_no",
    "cancelled_at",
    "cancellation_reason",
    "created_at",
}


def _normalized(value: object) -> str:
    return " ".join(str(value).split())


def test_task_change_request_columns_types_defaults_and_nullability() -> None:
    table = TaskChangeRequest.__table__

    assert table.name == "task_change_requests"
    assert set(table.columns.keys()) == FIELDS
    assert [column.name for column in table.primary_key.columns] == [
        "change_request_id"
    ]
    assert isinstance(table.c.change_request_id.type, Uuid)
    assert table.c.change_request_id.default is not None
    assert table.c.change_request_id.default.is_callable
    for field_name in ("task_id",):
        assert isinstance(table.c[field_name].type, Uuid)
    for field_name in (
        "patch_json",
        "before_snapshot",
        "after_snapshot",
    ):
        assert isinstance(table.c[field_name].type, JSONB)
    for field_name in (
        "requester_employee_no",
        "reason",
        "status",
        "decision_by_employee_no",
        "decision_comment",
        "cancelled_by_employee_no",
        "cancellation_reason",
    ):
        assert isinstance(table.c[field_name].type, String)
    for field_name in ("requester_task_version", "base_task_version"):
        assert isinstance(table.c[field_name].type, Integer)
    assert table.c.status.default.arg == "pending"
    optional = {
        "decision_by_employee_no",
        "decision_at",
        "decision_comment",
        "cancelled_by_employee_no",
        "cancelled_at",
        "cancellation_reason",
    }
    assert all(table.c[field].nullable is (field in optional) for field in FIELDS)


def test_task_change_request_timestamps_are_timezone_aware_and_utc() -> None:
    table = TaskChangeRequest.__table__
    for field_name in ("created_at", "decision_at", "cancelled_at"):
        assert isinstance(table.c[field_name].type, DateTime)
        assert table.c[field_name].type.timezone is True
    created_at = table.c.created_at
    assert created_at.default is not None
    value = created_at.default.arg(None)
    assert value.tzinfo is not None
    assert value.utcoffset() == timedelta(0)


def test_task_change_request_foreign_keys_are_restrict() -> None:
    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in TaskChangeRequest.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert foreign_keys == {
        (("task_id",), ("tasks.task_id",), "RESTRICT"),
        (("requester_employee_no",), ("users.employee_no",), "RESTRICT"),
        (("decision_by_employee_no",), ("users.employee_no",), "RESTRICT"),
        (("cancelled_by_employee_no",), ("users.employee_no",), "RESTRICT"),
    }


def test_task_change_request_checks_encode_frozen_lifecycle_invariants() -> None:
    checks = {
        constraint.name: _normalized(constraint.sqltext)
        for constraint in TaskChangeRequest.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert set(checks) == {
        "ck_task_change_requests_reason_non_blank",
        "ck_task_change_requests_patch_object_non_empty",
        "ck_task_change_requests_requester_task_version_positive",
        "ck_task_change_requests_base_task_version_positive",
        "ck_task_change_requests_status_allowed",
        "ck_task_change_requests_lifecycle_fields",
    }
    assert "'pending'" in checks["ck_task_change_requests_status_allowed"]
    assert "'approved'" in checks["ck_task_change_requests_status_allowed"]
    assert "'rejected'" in checks["ck_task_change_requests_status_allowed"]
    assert "'cancelled'" in checks["ck_task_change_requests_status_allowed"]
    assert "decision_by_employee_no IS NOT NULL" in checks[
        "ck_task_change_requests_lifecycle_fields"
    ]
    assert "cancellation_reason IS NOT NULL" in checks[
        "ck_task_change_requests_lifecycle_fields"
    ]


def test_task_change_request_indexes_include_one_pending_per_task() -> None:
    indexes = {index.name: index for index in TaskChangeRequest.__table__.indexes}
    assert set(indexes) == {
        "ix_task_change_requests_requester_timeline",
        "ix_task_change_requests_status_timeline",
        "ix_task_change_requests_task_status_timeline",
        "ix_task_change_requests_task_timeline",
        "uq_task_change_requests_one_pending_per_task",
    }
    partial = indexes["uq_task_change_requests_one_pending_per_task"]
    assert partial.unique is True
    assert tuple(column.name for column in partial.columns) == ("task_id",)
    assert "status = 'pending'" in _normalized(
        partial.dialect_options["postgresql"]["where"]
    )


def test_task_change_request_relationships_are_explicit_and_safe() -> None:
    relationships = inspect(TaskChangeRequest).relationships
    assert set(relationships.keys()) == {
        "task",
        "requester",
        "decision_by",
        "cancelled_by",
    }
    assert relationships.task.back_populates == "change_requests"
    assert relationships.task.mapper.class_ is Task
    assert relationships.requester.back_populates == "submitted_change_requests"
    assert relationships.requester.mapper.class_ is User
    assert relationships.decision_by.back_populates == "decided_change_requests"
    assert relationships.cancelled_by.back_populates == "cancelled_change_requests"
    for relationship in relationships:
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade

