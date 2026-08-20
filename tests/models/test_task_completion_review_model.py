from datetime import timedelta

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    inspect,
)

from app.models import Task, TaskCompletionReview, TaskNode, User

COMPLETION_REVIEW_FIELDS = {
    "completion_review_id",
    "task_id",
    "review_round",
    "submitted_by_employee_no",
    "completion_note",
    "deliverable_summary",
    "reviewer_employee_no",
    "review_status",
    "review_result",
    "reject_reason",
    "rework_node_id",
    "submitted_task_version",
    "reviewed_task_version",
    "submitted_at",
    "reviewed_at",
    "is_legacy_import",
}


def _normalized(value: object) -> str:
    return " ".join(str(value).split())


def test_completion_review_columns_types_defaults_and_nullability() -> None:
    table = TaskCompletionReview.__table__

    assert table.name == "task_completion_reviews"
    assert set(table.columns.keys()) == COMPLETION_REVIEW_FIELDS
    assert [column.name for column in table.primary_key.columns] == [
        "completion_review_id"
    ]
    assert isinstance(table.c.completion_review_id.type, Uuid)
    assert table.c.completion_review_id.default is not None
    assert table.c.completion_review_id.default.is_callable
    for field_name in ("task_id", "rework_node_id"):
        assert isinstance(table.c[field_name].type, Uuid)
    for field_name in (
        "review_round",
        "submitted_task_version",
        "reviewed_task_version",
    ):
        assert isinstance(table.c[field_name].type, Integer)
    for field_name in (
        "submitted_by_employee_no",
        "completion_note",
        "deliverable_summary",
        "reviewer_employee_no",
        "review_status",
        "review_result",
        "reject_reason",
    ):
        assert isinstance(table.c[field_name].type, String)
    assert isinstance(table.c.is_legacy_import.type, Boolean)
    assert table.c.review_status.default.arg == "submitted"
    assert table.c.is_legacy_import.default.arg is False

    optional_fields = {
        "completion_note",
        "deliverable_summary",
        "review_result",
        "reject_reason",
        "rework_node_id",
        "reviewed_task_version",
        "reviewed_at",
    }
    for field_name in COMPLETION_REVIEW_FIELDS:
        assert table.c[field_name].nullable is (field_name in optional_fields)


def test_completion_review_timestamps_are_timezone_aware_and_utc() -> None:
    table = TaskCompletionReview.__table__

    for field_name in ("submitted_at", "reviewed_at"):
        assert isinstance(table.c[field_name].type, DateTime)
        assert table.c[field_name].type.timezone is True
    submitted_at = table.c.submitted_at
    assert submitted_at.default is not None
    assert submitted_at.default.is_callable
    default_value = submitted_at.default.arg(None)
    assert default_value.tzinfo is not None
    assert default_value.utcoffset() == timedelta(0)


def test_completion_review_foreign_keys_are_restrict_and_same_task_safe() -> None:
    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in TaskCompletionReview.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }

    assert foreign_keys == {
        (("task_id",), ("tasks.task_id",), "RESTRICT"),
        (
            ("submitted_by_employee_no",),
            ("users.employee_no",),
            "RESTRICT",
        ),
        (("reviewer_employee_no",), ("users.employee_no",), "RESTRICT"),
        (
            ("task_id", "rework_node_id"),
            ("task_nodes.task_id", "task_nodes.node_id"),
            "RESTRICT",
        ),
    }


def test_completion_review_checks_encode_content_and_lifecycle() -> None:
    checks = {
        constraint.name: _normalized(constraint.sqltext)
        for constraint in TaskCompletionReview.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert set(checks) == {
        "ck_task_completion_reviews_completion_note_non_blank",
        "ck_task_completion_reviews_deliverable_summary_non_blank",
        "ck_task_completion_reviews_lifecycle_fields",
        "ck_task_completion_reviews_nonlegacy_content_present",
        "ck_task_completion_reviews_review_result_allowed",
        "ck_task_completion_reviews_review_round_positive",
        "ck_task_completion_reviews_review_status_allowed",
        "ck_task_completion_reviews_submitted_version_positive",
    }
    assert "review_round >= 1" in checks[
        "ck_task_completion_reviews_review_round_positive"
    ]
    assert "'submitted'" in checks[
        "ck_task_completion_reviews_review_status_allowed"
    ]
    assert "'approved'" in checks[
        "ck_task_completion_reviews_review_result_allowed"
    ]
    content = checks["ck_task_completion_reviews_nonlegacy_content_present"]
    assert "is_legacy_import" in content
    assert "completion_note IS NOT NULL" in content
    assert "deliverable_summary IS NOT NULL" in content
    lifecycle = checks["ck_task_completion_reviews_lifecycle_fields"]
    assert "review_status = 'submitted'" in lifecycle
    assert "review_status = 'approved'" in lifecycle
    assert "review_status = 'rejected'" in lifecycle
    assert "btrim(reject_reason) <> ''" in lifecycle
    assert "rework_node_id IS NULL" in lifecycle
    assert "reviewed_at >= submitted_at" in lifecycle
    assert "reviewed_task_version > submitted_task_version" in lifecycle


def test_completion_review_indexes_and_round_uniqueness() -> None:
    table = TaskCompletionReview.__table__
    indexes = {index.name: index for index in table.indexes}
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert unique_constraints == {("task_id", "review_round")}
    assert set(indexes) == {
        "ix_task_completion_reviews_reviewer_status_timeline",
        "ix_task_completion_reviews_rework_node",
        "ix_task_completion_reviews_submitter_timeline",
        "ix_task_completion_reviews_task_timeline",
        "uq_task_completion_reviews_one_submitted_per_task",
    }
    partial = indexes[
        "uq_task_completion_reviews_one_submitted_per_task"
    ]
    assert partial.unique is True
    assert tuple(column.name for column in partial.columns) == ("task_id",)
    assert "review_status = 'submitted'" in _normalized(
        partial.dialect_options["postgresql"]["where"]
    )
    assert tuple(
        column.name
        for column in indexes[
            "ix_task_completion_reviews_task_timeline"
        ].columns
    ) == (
        "task_id",
        "review_round",
        "submitted_at",
        "completion_review_id",
    )


def test_completion_review_relationships_are_explicit_and_safe() -> None:
    relationships = inspect(TaskCompletionReview).relationships

    assert set(relationships.keys()) == {
        "reviewer",
        "rework_node",
        "submitted_by",
        "task",
    }
    assert relationships.task.back_populates == "completion_reviews"
    assert relationships.task.mapper.class_ is Task
    assert relationships.submitted_by.back_populates == (
        "submitted_completion_reviews"
    )
    assert relationships.submitted_by.mapper.class_ is User
    assert relationships.reviewer.back_populates == "assigned_completion_reviews"
    assert relationships.reviewer.mapper.class_ is User
    assert relationships.rework_node.back_populates == (
        "rework_completion_reviews"
    )
    assert relationships.rework_node.mapper.class_ is TaskNode
    assert relationships.rework_node.viewonly is True
    for relationship in relationships:
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade
