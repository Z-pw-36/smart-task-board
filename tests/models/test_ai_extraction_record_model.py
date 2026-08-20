from sqlalchemy import DateTime, Numeric, UniqueConstraint, Uuid, inspect
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.models import AIExtractionRecord, Task, TaskInput


def test_metadata_contains_only_approved_business_tables() -> None:
    assert set(Base.metadata.tables) == {
        "ai_extraction_records",
        "departments",
        "task_inputs",
        "task_completion_reviews",
        "task_node_dependencies",
        "task_node_participants",
        "task_nodes",
        "task_participants",
        "task_progress_reports",
        "task_status_logs",
        "task_issues",
        "tasks",
        "users",
    }
    for table_name in (
        "boards",
        "workspaces",
        "projects",
        "task_change_requests",
        "performance_metrics",
        "task_performance_matches",
        "employee_profiles",
        "workload_snapshots",
        "task_priority_scores",
        "task_conflicts",
        "reminder_rules",
        "notifications",
        "task_archives",
        "operation_logs",
        "user_authorized_scopes",
        "system_parameters",
        "attachments",
        "ai_conversations",
        "ai_conversation_messages",
    ):
        assert table_name not in Base.metadata.tables


def test_ai_extraction_columns_and_primary_key_contract() -> None:
    table = AIExtractionRecord.__table__

    assert table.name == "ai_extraction_records"
    assert set(table.columns.keys()) == {
        "extraction_id",
        "input_id",
        "task_id",
        "extracted_json",
        "missing_fields",
        "low_confidence_fields",
        "confirm_questions",
        "confidence_score",
        "confirmed_at",
    }
    assert [column.name for column in table.primary_key.columns] == [
        "extraction_id"
    ]
    assert isinstance(table.c.extraction_id.type, Uuid)
    assert table.c.extraction_id.default is not None
    assert table.c.extraction_id.default.is_callable
    assert "id" not in table.columns


def test_ai_extraction_input_foreign_key_and_one_to_many_relationship() -> None:
    input_id = AIExtractionRecord.__table__.c.input_id
    foreign_key = next(iter(input_id.foreign_keys))
    extraction_relationship = inspect(AIExtractionRecord).relationships.input
    input_relationship = inspect(TaskInput).relationships.ai_extraction_records

    assert input_id.nullable is False
    assert foreign_key.target_fullname == "task_inputs.input_id"
    assert foreign_key.ondelete == "RESTRICT"
    assert extraction_relationship.back_populates == "ai_extraction_records"
    assert extraction_relationship.uselist is False
    assert {item.name for item in extraction_relationship.local_columns} == {
        "input_id"
    }
    assert input_relationship.back_populates == "input"
    assert input_relationship.uselist is True

    for relationship in (extraction_relationship, input_relationship):
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade


def test_ai_extraction_task_foreign_key_and_many_to_one_relationship() -> None:
    table = AIExtractionRecord.__table__
    task_id = table.c.task_id
    foreign_key = next(iter(task_id.foreign_keys))
    extraction_relationship = inspect(AIExtractionRecord).relationships.task
    task_relationship = inspect(Task).relationships.ai_extraction_records
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert task_id.nullable is True
    assert foreign_key.target_fullname == "tasks.task_id"
    assert foreign_key.ondelete == "RESTRICT"
    assert ("task_id",) not in unique_constraints
    assert task_id.unique is not True
    assert extraction_relationship.back_populates == "ai_extraction_records"
    assert extraction_relationship.uselist is False
    assert task_relationship.back_populates == "task"
    assert task_relationship.uselist is True

    for relationship in (extraction_relationship, task_relationship):
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade


def test_ai_extraction_json_fields_use_safe_callable_defaults() -> None:
    table = AIExtractionRecord.__table__
    expected_defaults = {
        "extracted_json": {},
        "missing_fields": [],
        "low_confidence_fields": [],
        "confirm_questions": [],
    }

    for field_name, expected_value in expected_defaults.items():
        column = table.c[field_name]
        assert isinstance(column.type, JSONB)
        assert column.nullable is False
        assert column.default is not None
        assert column.default.is_callable

        first_value = column.default.arg(None)
        second_value = column.default.arg(None)
        assert first_value == expected_value
        assert second_value == expected_value
        assert first_value is not second_value


def test_ai_extraction_confidence_and_confirmation_time_types() -> None:
    table = AIExtractionRecord.__table__
    confidence_score = table.c.confidence_score
    confirmed_at = table.c.confirmed_at

    assert isinstance(confidence_score.type, Numeric)
    assert confidence_score.type.precision is None
    assert confidence_score.type.scale is None
    assert confidence_score.nullable is True
    assert isinstance(confirmed_at.type, DateTime)
    assert confirmed_at.type.timezone is True
    assert confirmed_at.nullable is True


def test_ai_extraction_indexes_are_non_redundant() -> None:
    indexed_columns = {
        tuple(column.name for column in index.columns)
        for index in AIExtractionRecord.__table__.indexes
    }

    assert indexed_columns == {("input_id",), ("task_id",)}
    assert ("extraction_id",) not in indexed_columns
    assert ("confirmed_at",) not in indexed_columns
