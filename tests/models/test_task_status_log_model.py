import warnings
from datetime import timedelta

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Uuid, inspect
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import configure_mappers

from app.models import Task, TaskStatusLog, User

TASK_STATUS_LOG_FIELDS = {
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
}


def test_task_status_log_columns_and_primary_key_contract() -> None:
    table = TaskStatusLog.__table__

    assert table.name == "task_status_logs"
    assert set(table.columns.keys()) == TASK_STATUS_LOG_FIELDS
    assert len(TASK_STATUS_LOG_FIELDS) == 13
    assert [column.name for column in table.primary_key.columns] == ["status_log_id"]
    assert isinstance(table.c.status_log_id.type, Uuid)
    assert table.c.status_log_id.default is not None
    assert table.c.status_log_id.default.is_callable
    for forbidden_field in (
        "id",
        "user_id",
        "employee_id",
        "target_user_id",
        "target_employee_id",
        "reject_reason",
        "updated_at",
        "deleted_at",
        "request_id",
        "idempotency_key",
    ):
        assert forbidden_field not in table.columns


def test_task_status_log_foreign_keys_are_explicit_restrict_and_nullable() -> None:
    table = TaskStatusLog.__table__
    expected = {
        "task_id": ("tasks.task_id", False),
        "operator_employee_no": ("users.employee_no", True),
        "target_employee_no": ("users.employee_no", True),
    }

    for field_name, (target, nullable) in expected.items():
        column = table.c[field_name]
        foreign_key = next(iter(column.foreign_keys))
        assert foreign_key.target_fullname == target
        assert foreign_key.ondelete == "RESTRICT"
        assert column.nullable is nullable


def test_task_status_log_string_integer_and_uuid_field_contract() -> None:
    table = TaskStatusLog.__table__

    for field_name in (
        "from_status",
        "to_status",
        "action_type",
        "reason",
        "operator_employee_no",
        "target_employee_no",
        "business_ref_type",
        "operation_source",
    ):
        assert isinstance(table.c[field_name].type, String)
        assert table.c[field_name].type.length is None

    assert table.c.from_status.nullable is True
    assert table.c.to_status.nullable is False
    assert table.c.action_type.nullable is False
    assert table.c.reason.nullable is True
    assert isinstance(table.c.task_version.type, Integer)
    assert table.c.task_version.nullable is False
    assert table.c.business_ref_type.nullable is True
    assert isinstance(table.c.business_ref_id.type, Uuid)
    assert table.c.business_ref_id.nullable is True
    assert table.c.operation_source.nullable is False


def test_task_status_log_has_only_approved_check_constraints() -> None:
    checks = {
        constraint.name: " ".join(str(constraint.sqltext).split())
        for constraint in TaskStatusLog.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert set(checks) == {
        "ck_task_status_logs_business_ref_pair",
        "ck_task_status_logs_task_version_positive",
    }
    assert checks["ck_task_status_logs_task_version_positive"] == "task_version >= 1"
    business_ref_check = checks["ck_task_status_logs_business_ref_pair"]
    assert "business_ref_type IS NULL AND business_ref_id IS NULL" in business_ref_check
    assert (
        "business_ref_type IS NOT NULL AND business_ref_id IS NOT NULL"
        in business_ref_check
    )
    assert "from_status <> to_status" not in business_ref_check


def test_task_status_log_indexes_are_exact_and_non_redundant() -> None:
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in TaskStatusLog.__table__.indexes
    }

    assert indexes == {
        "ix_task_status_logs_action_type": ("action_type",),
        "ix_task_status_logs_business_ref": (
            "business_ref_type",
            "business_ref_id",
        ),
        "ix_task_status_logs_operator_employee_no": ("operator_employee_no",),
        "ix_task_status_logs_target_employee_no": ("target_employee_no",),
        "ix_task_status_logs_task_timeline": (
            "task_id",
            "created_at",
            "status_log_id",
        ),
    }
    assert ("task_id",) not in indexes.values()
    assert ("created_at",) not in indexes.values()
    assert ("business_ref_id",) not in indexes.values()


def test_task_status_log_created_at_is_timezone_aware_with_utc_callable() -> None:
    created_at = TaskStatusLog.__table__.c.created_at

    assert isinstance(created_at.type, DateTime)
    assert created_at.type.timezone is True
    assert created_at.nullable is False
    assert created_at.default is not None
    assert created_at.default.is_callable
    default_value = created_at.default.arg(None)
    assert default_value.tzinfo is not None
    assert default_value.utcoffset() == timedelta(0)


def test_task_status_log_relationships_are_bidirectional_unambiguous_and_safe() -> None:
    relationships = inspect(TaskStatusLog).relationships

    assert set(relationships.keys()) == {"operator", "target_employee", "task"}
    assert relationships.task.back_populates == "status_logs"
    assert relationships.task.mapper.class_ is Task
    assert {column.name for column in relationships.task.local_columns} == {"task_id"}
    assert relationships.operator.back_populates == "operated_task_status_logs"
    assert relationships.operator.mapper.class_ is User
    assert {column.name for column in relationships.operator.local_columns} == {
        "operator_employee_no"
    }
    assert relationships.target_employee.back_populates == "targeted_task_status_logs"
    assert relationships.target_employee.mapper.class_ is User
    assert {column.name for column in relationships.target_employee.local_columns} == {
        "target_employee_no"
    }

    for relationship in relationships:
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade


def test_task_status_log_mappers_configure_without_sqlalchemy_warnings() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", SAWarning)
        configure_mappers()

    mapping_warnings = [
        item for item in caught if issubclass(item.category, SAWarning)
    ]
    assert mapping_warnings == []
