from datetime import timedelta

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    inspect,
)

from app.models import Task, TaskIssue, TaskNode, TaskProgressReport, User

PROGRESS_REPORT_FIELDS = {
    "progress_report_id",
    "task_id",
    "node_id",
    "reporter_employee_no",
    "progress_percent",
    "report_content",
    "stage_result",
    "difficulty",
    "resource_request",
    "actual_hours",
    "corrects_report_id",
    "report_period_start",
    "report_period_end",
    "task_version",
    "operation_source",
    "created_at",
}


def _normalized(value: object) -> str:
    return " ".join(str(value).split())


def test_progress_report_columns_types_and_nullability() -> None:
    table = TaskProgressReport.__table__

    assert table.name == "task_progress_reports"
    assert set(table.columns.keys()) == PROGRESS_REPORT_FIELDS
    assert [column.name for column in table.primary_key.columns] == [
        "progress_report_id"
    ]
    assert isinstance(table.c.progress_report_id.type, Uuid)
    assert table.c.progress_report_id.default is not None
    assert table.c.progress_report_id.default.is_callable
    assert isinstance(table.c.task_id.type, Uuid)
    assert isinstance(table.c.node_id.type, Uuid)
    assert isinstance(table.c.corrects_report_id.type, Uuid)
    assert isinstance(table.c.progress_percent.type, Integer)
    assert isinstance(table.c.task_version.type, Integer)
    assert isinstance(table.c.actual_hours.type, Numeric)
    for field_name in (
        "reporter_employee_no",
        "report_content",
        "stage_result",
        "difficulty",
        "resource_request",
        "operation_source",
    ):
        assert isinstance(table.c[field_name].type, String)
    for field_name in (
        "node_id",
        "stage_result",
        "difficulty",
        "resource_request",
        "actual_hours",
        "corrects_report_id",
        "report_period_start",
        "report_period_end",
    ):
        assert table.c[field_name].nullable is True
    assert all(
        table.c[field_name].nullable is False
        for field_name in PROGRESS_REPORT_FIELDS
        if field_name
        not in {
            "node_id",
            "stage_result",
            "difficulty",
            "resource_request",
            "actual_hours",
            "corrects_report_id",
            "report_period_start",
            "report_period_end",
        }
    )


def test_progress_report_timestamps_are_timezone_aware_and_created_at_is_utc() -> None:
    table = TaskProgressReport.__table__

    for field_name in (
        "report_period_start",
        "report_period_end",
        "created_at",
    ):
        assert isinstance(table.c[field_name].type, DateTime)
        assert table.c[field_name].type.timezone is True
    created_at = table.c.created_at
    assert created_at.default is not None
    assert created_at.default.is_callable
    default_value = created_at.default.arg(None)
    assert default_value.tzinfo is not None
    assert default_value.utcoffset() == timedelta(0)


def test_progress_report_foreign_keys_are_restrict_and_same_task_safe() -> None:
    table = TaskProgressReport.__table__
    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }

    assert foreign_keys == {
        (("task_id",), ("tasks.task_id",), "RESTRICT"),
        (("reporter_employee_no",), ("users.employee_no",), "RESTRICT"),
        (
            ("task_id", "node_id"),
            ("task_nodes.task_id", "task_nodes.node_id"),
            "RESTRICT",
        ),
        (
            ("task_id", "corrects_report_id"),
            (
                "task_progress_reports.task_id",
                "task_progress_reports.progress_report_id",
            ),
            "RESTRICT",
        ),
    }
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_constraints == {("task_id", "progress_report_id")}


def test_progress_report_check_constraints_encode_frozen_invariants() -> None:
    checks = {
        constraint.name: _normalized(constraint.sqltext)
        for constraint in TaskProgressReport.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert set(checks) == {
        "ck_task_progress_reports_actual_hours_non_negative",
        "ck_task_progress_reports_content_non_blank",
        "ck_task_progress_reports_node_period_absent",
        "ck_task_progress_reports_not_self_correction",
        "ck_task_progress_reports_operation_source_non_blank",
        "ck_task_progress_reports_period_order",
        "ck_task_progress_reports_period_pair",
        "ck_task_progress_reports_progress_percent_range",
        "ck_task_progress_reports_task_version_positive",
    }
    assert "BETWEEN 0 AND 100" in checks[
        "ck_task_progress_reports_progress_percent_range"
    ]
    assert "btrim(report_content) <> ''" in checks[
        "ck_task_progress_reports_content_non_blank"
    ]
    assert "actual_hours >= 0" in checks[
        "ck_task_progress_reports_actual_hours_non_negative"
    ]
    assert "corrects_report_id <> progress_report_id" in checks[
        "ck_task_progress_reports_not_self_correction"
    ]
    assert "report_period_end > report_period_start" in checks[
        "ck_task_progress_reports_period_order"
    ]
    assert "node_id IS NULL" in checks[
        "ck_task_progress_reports_node_period_absent"
    ]
    assert "report_period_start IS NULL" in checks[
        "ck_task_progress_reports_node_period_absent"
    ]
    assert "report_period_end IS NULL" in checks[
        "ck_task_progress_reports_node_period_absent"
    ]
    assert "task_version >= 1" in checks[
        "ck_task_progress_reports_task_version_positive"
    ]


def test_progress_report_indexes_include_partial_task_period_uniqueness() -> None:
    indexes = {index.name: index for index in TaskProgressReport.__table__.indexes}

    assert set(indexes) == {
        "ix_task_progress_reports_corrects_report_id",
        "ix_task_progress_reports_node_timeline",
        "ix_task_progress_reports_reporter_timeline",
        "ix_task_progress_reports_task_timeline",
        "uq_task_progress_reports_one_current_task_period",
    }
    assert tuple(
        column.name for column in indexes["ix_task_progress_reports_task_timeline"].columns
    ) == ("task_id", "created_at", "progress_report_id")
    assert tuple(
        column.name for column in indexes["ix_task_progress_reports_node_timeline"].columns
    ) == ("task_id", "node_id", "created_at", "progress_report_id")
    partial = indexes["uq_task_progress_reports_one_current_task_period"]
    assert partial.unique is True
    assert tuple(column.name for column in partial.columns) == (
        "task_id",
        "report_period_end",
    )
    where = _normalized(partial.dialect_options["postgresql"]["where"])
    assert "node_id IS NULL" in where
    assert "corrects_report_id IS NULL" in where
    assert "report_period_end IS NOT NULL" in where


def test_progress_report_relationships_are_explicit_and_safe() -> None:
    relationships = inspect(TaskProgressReport).relationships

    assert set(relationships.keys()) == {
        "corrections",
        "corrects_report",
        "issues",
        "node",
        "reporter",
        "task",
    }
    assert relationships.task.back_populates == "progress_reports"
    assert relationships.task.mapper.class_ is Task
    assert relationships.node.back_populates == "progress_reports"
    assert relationships.node.mapper.class_ is TaskNode
    assert relationships.node.viewonly is True
    assert relationships.reporter.back_populates == "submitted_progress_reports"
    assert relationships.reporter.mapper.class_ is User
    assert relationships.corrects_report.back_populates == "corrections"
    assert relationships.corrects_report.uselist is False
    assert relationships.corrects_report.viewonly is True
    assert relationships.corrections.back_populates == "corrects_report"
    assert relationships.corrections.uselist is True
    assert relationships.corrections.viewonly is True
    assert relationships.issues.back_populates == "source_progress_report"
    assert relationships.issues.mapper.class_ is TaskIssue
    assert relationships.issues.viewonly is True
    for relationship in relationships:
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade
