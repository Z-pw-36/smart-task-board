from datetime import timedelta

from sqlalchemy import DateTime, String, Uuid, inspect

from app.models import TaskInput, User


def test_task_input_columns_and_primary_key_contract() -> None:
    table = TaskInput.__table__

    assert table.name == "task_inputs"
    assert set(table.columns.keys()) == {
        "input_id",
        "input_type",
        "raw_text",
        "voice_file_url",
        "asr_text",
        "source_channel",
        "submitted_by_employee_no",
        "submitted_at",
    }
    assert [column.name for column in table.primary_key.columns] == ["input_id"]
    assert isinstance(table.c.input_id.type, Uuid)
    assert table.c.input_id.default is not None
    assert table.c.input_id.default.is_callable
    assert "id" not in table.columns
    assert "user_id" not in table.columns
    assert "employee_id" not in table.columns


def test_task_input_string_fields_and_nullability() -> None:
    table = TaskInput.__table__

    for field_name in (
        "input_type",
        "raw_text",
        "voice_file_url",
        "asr_text",
        "source_channel",
        "submitted_by_employee_no",
    ):
        assert isinstance(table.c[field_name].type, String)
        assert table.c[field_name].type.length is None

    assert table.c.input_type.nullable is False
    assert table.c.raw_text.nullable is True
    assert table.c.voice_file_url.nullable is True
    assert table.c.asr_text.nullable is True
    assert table.c.source_channel.nullable is False
    assert table.c.submitted_by_employee_no.nullable is False


def test_task_input_submitter_foreign_key_and_relationships() -> None:
    column = TaskInput.__table__.c.submitted_by_employee_no
    foreign_key = next(iter(column.foreign_keys))
    task_input_relationships = inspect(TaskInput).relationships
    user_relationship = inspect(User).relationships.submitted_task_inputs

    assert foreign_key.target_fullname == "users.employee_no"
    assert foreign_key.ondelete == "RESTRICT"
    assert task_input_relationships.submitted_by.back_populates == (
        "submitted_task_inputs"
    )
    assert task_input_relationships.submitted_by.uselist is False
    assert {item.name for item in task_input_relationships.submitted_by.local_columns} == {
        "submitted_by_employee_no"
    }
    assert user_relationship.back_populates == "submitted_by"
    assert user_relationship.uselist is True

    for relationship in (
        task_input_relationships.submitted_by,
        user_relationship,
    ):
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade


def test_task_input_submitted_at_is_timezone_aware_and_utc_by_default() -> None:
    submitted_at = TaskInput.__table__.c.submitted_at

    assert isinstance(submitted_at.type, DateTime)
    assert submitted_at.type.timezone is True
    assert submitted_at.nullable is False
    assert submitted_at.default is not None
    assert submitted_at.default.is_callable

    default_value = submitted_at.default.arg(None)
    assert default_value.tzinfo is not None
    assert default_value.utcoffset() == timedelta(0)


def test_task_input_indexes_are_non_redundant() -> None:
    indexed_columns = {
        tuple(column.name for column in index.columns)
        for index in TaskInput.__table__.indexes
    }

    assert indexed_columns == {
        ("submitted_at",),
        ("submitted_by_employee_no",),
    }
    assert ("input_id",) not in indexed_columns
    assert ("source_channel",) not in indexed_columns
