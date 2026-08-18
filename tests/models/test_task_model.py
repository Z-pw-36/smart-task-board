from datetime import timedelta

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    inspect,
)

from app.models import (
    AIExtractionRecord,
    Department,
    Task,
    TaskNode,
    TaskNodeDependency,
    TaskParticipant,
    TaskStatusLog,
    User,
)

TASK_FIELDS = {
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
}


def test_task_columns_and_primary_key_contract() -> None:
    table = Task.__table__

    assert table.name == "tasks"
    assert set(table.columns.keys()) == TASK_FIELDS
    assert len(TASK_FIELDS) == 34
    assert [column.name for column in table.primary_key.columns] == ["task_id"]
    assert isinstance(table.c.task_id.type, Uuid)
    assert table.c.task_id.default is not None
    assert table.c.task_id.default.is_callable
    assert "id" not in table.columns
    assert "user_id" not in table.columns
    assert "employee_id" not in table.columns


def test_task_forbidden_phase_1c_fields_are_absent() -> None:
    columns = Task.__table__.columns

    for field_name in (
        "report_weekday",
        "report_time",
        "report_timezone",
        "last_report_at",
        "next_report_at",
        "source_extraction_id",
        "version_no",
        "is_blocked",
        "is_pending_report",
    ):
        assert field_name not in columns


def test_task_string_fields_and_nullability() -> None:
    table = Task.__table__
    required_strings = {"task_name", "creator_employee_no", "status"}
    optional_strings = {
        "task_no",
        "task_description",
        "task_goal",
        "task_source",
        "main_assignee_employee_no",
        "report_to_employee_no",
        "report_to_level",
        "reviewer_employee_no",
        "deliverable",
        "acceptance_criteria",
        "report_cycle",
        "cancel_reason",
        "withdraw_reason",
        "close_reason",
    }

    for field_name in required_strings | optional_strings:
        column = table.c[field_name]
        assert isinstance(column.type, String)
        assert column.type.length is None
        assert column.nullable is (field_name not in required_strings)

    assert isinstance(table.c.is_urgent.type, Boolean)
    assert table.c.is_urgent.nullable is True
    assert table.c.acceptance_criteria.nullable is True


def test_task_foreign_keys_use_explicit_business_identifiers() -> None:
    table = Task.__table__
    expected_foreign_keys = {
        "creator_employee_no": "users.employee_no",
        "main_assignee_employee_no": "users.employee_no",
        "report_to_employee_no": "users.employee_no",
        "reviewer_employee_no": "users.employee_no",
        "department_id": "departments.department_id",
        "merged_into_task_id": "tasks.task_id",
    }

    for field_name, target in expected_foreign_keys.items():
        foreign_key = next(iter(table.c[field_name].foreign_keys))
        assert foreign_key.target_fullname == target
        assert foreign_key.ondelete == "RESTRICT"

    assert table.c.creator_employee_no.nullable is False
    for field_name in expected_foreign_keys.keys() - {"creator_employee_no"}:
        assert table.c[field_name].nullable is True


def test_task_defaults_numeric_types_and_check_constraints() -> None:
    table = Task.__table__
    check_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert isinstance(table.c.estimated_hours.type, Numeric)
    assert isinstance(table.c.actual_hours.type, Numeric)
    assert table.c.estimated_hours.type.precision is None
    assert table.c.actual_hours.type.precision is None
    assert isinstance(table.c.task_weight.type, Integer)
    assert isinstance(table.c.task_version.type, Integer)
    assert table.c.status.default.arg == "draft"
    assert table.c.task_version.default.arg == 1
    assert set(check_constraints) == {
        "ck_tasks_actual_hours_non_negative",
        "ck_tasks_estimated_hours_non_negative",
        "ck_tasks_not_merged_into_self",
        "ck_tasks_task_version_positive",
        "ck_tasks_task_weight_range",
    }
    assert "actual_hours >= 0" in check_constraints[
        "ck_tasks_actual_hours_non_negative"
    ]
    assert "estimated_hours >= 0" in check_constraints[
        "ck_tasks_estimated_hours_non_negative"
    ]
    assert "BETWEEN 1 AND 5" in check_constraints["ck_tasks_task_weight_range"]
    assert "merged_into_task_id <> task_id" in check_constraints[
        "ck_tasks_not_merged_into_self"
    ]
    assert "task_version >= 1" in check_constraints[
        "ck_tasks_task_version_positive"
    ]


def test_task_timestamp_columns_are_timezone_aware_with_utc_defaults() -> None:
    table = Task.__table__
    timestamp_fields = {
        "start_time",
        "deadline",
        "created_at",
        "updated_at",
        "confirmed_at",
        "sent_at",
        "accepted_at",
        "completed_at",
        "archived_at",
    }

    for field_name in timestamp_fields:
        column = table.c[field_name]
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.nullable is (field_name not in {"created_at", "updated_at"})

    for field_name in ("created_at", "updated_at"):
        column = table.c[field_name]
        assert column.default is not None
        assert column.default.is_callable
        default_value = column.default.arg(None)
        assert default_value.tzinfo is not None
        assert default_value.utcoffset() == timedelta(0)

    assert table.c.updated_at.onupdate is not None
    assert table.c.updated_at.onupdate.is_callable


def test_task_number_unique_constraint_and_indexes_are_non_redundant() -> None:
    table = Task.__table__
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexed_columns = {
        tuple(column.name for column in index.columns) for index in table.indexes
    }

    assert table.c.task_no.nullable is True
    assert unique_constraints == {("task_no",)}
    assert ("task_no",) not in indexed_columns
    assert indexed_columns == {
        ("created_at",),
        ("creator_employee_no",),
        ("deadline",),
        ("department_id",),
        ("main_assignee_employee_no",),
        ("merged_into_task_id",),
        ("report_to_employee_no",),
        ("reviewer_employee_no",),
        ("status",),
    }
    assert ("task_id",) not in indexed_columns


def test_task_relationships_are_explicit_bidirectional_and_safe() -> None:
    relationships = inspect(Task).relationships
    expected_relationships = {
        "ai_extraction_records",
        "creator",
        "department",
        "main_assignee",
        "merged_from_tasks",
        "merged_into_task",
        "node_dependencies",
        "nodes",
        "participants",
        "report_to",
        "reviewer",
        "status_logs",
    }

    assert set(relationships.keys()) == expected_relationships
    user_relationships = {
        "creator": ("created_tasks", "creator_employee_no"),
        "main_assignee": ("assigned_tasks", "main_assignee_employee_no"),
        "report_to": ("reporting_tasks", "report_to_employee_no"),
        "reviewer": ("review_tasks", "reviewer_employee_no"),
    }
    for relationship_name, (back_populates, local_column) in (
        user_relationships.items()
    ):
        relationship = relationships[relationship_name]
        assert relationship.back_populates == back_populates
        assert relationship.mapper.class_ is User
        assert {column.name for column in relationship.local_columns} == {
            local_column
        }

    assert relationships.department.back_populates == "tasks"
    assert relationships.department.mapper.class_ is Department
    assert relationships.participants.back_populates == "task"
    assert relationships.participants.mapper.class_ is TaskParticipant
    assert relationships.participants.uselist is True
    assert relationships.nodes.back_populates == "task"
    assert relationships.nodes.mapper.class_ is TaskNode
    assert relationships.nodes.uselist is True
    assert tuple(expression.name for expression in relationships.nodes.order_by) == (
        "node_order",
        "sort_weight",
        "node_id",
    )
    assert relationships.node_dependencies.back_populates == "task"
    assert relationships.node_dependencies.mapper.class_ is TaskNodeDependency
    assert relationships.node_dependencies.uselist is True
    assert relationships.status_logs.back_populates == "task"
    assert relationships.status_logs.mapper.class_ is TaskStatusLog
    assert relationships.status_logs.uselist is True
    assert tuple(
        expression.name for expression in relationships.status_logs.order_by
    ) == ("created_at", "status_log_id")
    assert relationships.ai_extraction_records.back_populates == "task"
    assert relationships.ai_extraction_records.mapper.class_ is AIExtractionRecord
    assert relationships.ai_extraction_records.uselist is True
    assert relationships.merged_into_task.back_populates == "merged_from_tasks"
    assert relationships.merged_into_task.uselist is False
    assert {column.name for column in relationships.merged_into_task.remote_side} == {
        "task_id"
    }
    assert relationships.merged_from_tasks.back_populates == "merged_into_task"
    assert relationships.merged_from_tasks.uselist is True

    for relationship_name in expected_relationships:
        cascade = relationships[relationship_name].cascade
        assert "delete" not in cascade
        assert "delete-orphan" not in cascade
