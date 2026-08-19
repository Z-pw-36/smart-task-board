from datetime import timedelta

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    inspect,
)

from app.models import Task, TaskIssue, TaskNode, TaskProgressReport, User

TASK_ISSUE_FIELDS = {
    "issue_id",
    "task_id",
    "node_id",
    "source_progress_report_id",
    "reported_by_employee_no",
    "issue_type",
    "title",
    "description",
    "requested_resource",
    "severity",
    "status",
    "owner_employee_no",
    "resolution_note",
    "resolved_by_employee_no",
    "rejected_by_employee_no",
    "closed_by_employee_no",
    "created_at",
    "processing_started_at",
    "resolved_at",
    "rejected_at",
    "closed_at",
}


def _normalized(value: object) -> str:
    return " ".join(str(value).split())


def test_task_issue_columns_types_defaults_and_nullability() -> None:
    table = TaskIssue.__table__

    assert table.name == "task_issues"
    assert set(table.columns.keys()) == TASK_ISSUE_FIELDS
    assert [column.name for column in table.primary_key.columns] == ["issue_id"]
    assert isinstance(table.c.issue_id.type, Uuid)
    assert table.c.issue_id.default is not None
    assert table.c.issue_id.default.is_callable
    for field_name in ("task_id", "node_id", "source_progress_report_id"):
        assert isinstance(table.c[field_name].type, Uuid)
    for field_name in (
        "reported_by_employee_no",
        "issue_type",
        "title",
        "description",
        "requested_resource",
        "severity",
        "status",
        "owner_employee_no",
        "resolution_note",
        "resolved_by_employee_no",
        "rejected_by_employee_no",
        "closed_by_employee_no",
    ):
        assert isinstance(table.c[field_name].type, String)
    assert table.c.status.default.arg == "open"
    optional_fields = {
        "node_id",
        "source_progress_report_id",
        "requested_resource",
        "resolution_note",
        "resolved_by_employee_no",
        "rejected_by_employee_no",
        "closed_by_employee_no",
        "processing_started_at",
        "resolved_at",
        "rejected_at",
        "closed_at",
    }
    for field_name in TASK_ISSUE_FIELDS:
        assert table.c[field_name].nullable is (field_name in optional_fields)


def test_task_issue_timestamps_are_timezone_aware_and_created_at_is_utc() -> None:
    table = TaskIssue.__table__
    for field_name in (
        "created_at",
        "processing_started_at",
        "resolved_at",
        "rejected_at",
        "closed_at",
    ):
        assert isinstance(table.c[field_name].type, DateTime)
        assert table.c[field_name].type.timezone is True
    created_at = table.c.created_at
    assert created_at.default is not None
    assert created_at.default.is_callable
    default_value = created_at.default.arg(None)
    assert default_value.tzinfo is not None
    assert default_value.utcoffset() == timedelta(0)


def test_task_issue_foreign_keys_are_restrict_and_same_task_safe() -> None:
    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in TaskIssue.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }

    assert foreign_keys == {
        (("task_id",), ("tasks.task_id",), "RESTRICT"),
        (("reported_by_employee_no",), ("users.employee_no",), "RESTRICT"),
        (("owner_employee_no",), ("users.employee_no",), "RESTRICT"),
        (("resolved_by_employee_no",), ("users.employee_no",), "RESTRICT"),
        (("rejected_by_employee_no",), ("users.employee_no",), "RESTRICT"),
        (("closed_by_employee_no",), ("users.employee_no",), "RESTRICT"),
        (
            ("task_id", "node_id"),
            ("task_nodes.task_id", "task_nodes.node_id"),
            "RESTRICT",
        ),
        (
            ("task_id", "source_progress_report_id"),
            (
                "task_progress_reports.task_id",
                "task_progress_reports.progress_report_id",
            ),
            "RESTRICT",
        ),
    }


def test_task_issue_checks_encode_types_and_static_lifecycle_invariants() -> None:
    checks = {
        constraint.name: _normalized(constraint.sqltext)
        for constraint in TaskIssue.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert set(checks) == {
        "ck_task_issues_active_lifecycle_fields_absent",
        "ck_task_issues_closed_fields",
        "ck_task_issues_description_non_blank",
        "ck_task_issues_issue_type_allowed",
        "ck_task_issues_open_not_processing",
        "ck_task_issues_processing_started",
        "ck_task_issues_rejected_exclusive",
        "ck_task_issues_rejected_fields",
        "ck_task_issues_resource_request_requires_resource",
        "ck_task_issues_resolved_exclusive",
        "ck_task_issues_resolved_fields",
        "ck_task_issues_severity_allowed",
        "ck_task_issues_status_allowed",
        "ck_task_issues_title_non_blank",
    }
    assert "'blocker'" in checks["ck_task_issues_issue_type_allowed"]
    assert "'resource_request'" in checks["ck_task_issues_issue_type_allowed"]
    assert "'collaboration_support'" in checks[
        "ck_task_issues_issue_type_allowed"
    ]
    assert "'risk'" in checks["ck_task_issues_issue_type_allowed"]
    assert "requested_resource IS NOT NULL" in checks[
        "ck_task_issues_resource_request_requires_resource"
    ]
    assert "'critical'" in checks["ck_task_issues_severity_allowed"]
    assert "'processing'" in checks["ck_task_issues_status_allowed"]
    assert "processing_started_at IS NOT NULL" in checks[
        "ck_task_issues_processing_started"
    ]
    assert "resolved_by_employee_no IS NOT NULL" in checks[
        "ck_task_issues_resolved_fields"
    ]
    assert "rejected_by_employee_no IS NOT NULL" in checks[
        "ck_task_issues_rejected_fields"
    ]
    assert "closed_by_employee_no IS NOT NULL" in checks[
        "ck_task_issues_closed_fields"
    ]
    assert "status NOT IN ('open', 'processing')" in checks[
        "ck_task_issues_active_lifecycle_fields_absent"
    ]


def test_task_issue_indexes_cover_timelines_and_active_node_lookup() -> None:
    indexes = {index.name: index for index in TaskIssue.__table__.indexes}
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in TaskIssue.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert set(indexes) == {
        "ix_task_issues_active_task_node",
        "ix_task_issues_node_status",
        "ix_task_issues_owner_status_timeline",
        "ix_task_issues_source_progress_report_id",
        "ix_task_issues_task_status_timeline",
        "ix_task_issues_task_timeline",
    }
    assert tuple(
        column.name for column in indexes["ix_task_issues_task_timeline"].columns
    ) == ("task_id", "created_at", "issue_id")
    assert tuple(
        column.name
        for column in indexes["ix_task_issues_task_status_timeline"].columns
    ) == ("task_id", "status", "created_at", "issue_id")
    active = indexes["ix_task_issues_active_task_node"]
    assert active.unique is False
    assert unique_constraints == set()
    assert tuple(column.name for column in active.columns) == ("task_id", "node_id")
    where = _normalized(active.dialect_options["postgresql"]["where"])
    assert "status IN ('open', 'processing')" in where


def test_task_issue_relationships_are_explicit_and_safe() -> None:
    relationships = inspect(TaskIssue).relationships

    assert set(relationships.keys()) == {
        "closed_by",
        "node",
        "owner",
        "rejected_by",
        "reported_by",
        "resolved_by",
        "source_progress_report",
        "task",
    }
    assert relationships.task.back_populates == "issues"
    assert relationships.task.mapper.class_ is Task
    assert relationships.node.back_populates == "issues"
    assert relationships.node.mapper.class_ is TaskNode
    assert relationships.node.viewonly is True
    assert relationships.source_progress_report.back_populates == "issues"
    assert relationships.source_progress_report.mapper.class_ is TaskProgressReport
    assert relationships.source_progress_report.viewonly is True
    user_relationships = {
        "reported_by": "reported_task_issues",
        "owner": "owned_task_issues",
        "resolved_by": "resolved_task_issues",
        "rejected_by": "rejected_task_issues",
        "closed_by": "closed_task_issues",
    }
    for relationship_name, back_populates in user_relationships.items():
        relationship = relationships[relationship_name]
        assert relationship.back_populates == back_populates
        assert relationship.mapper.class_ is User
    for relationship in relationships:
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade
