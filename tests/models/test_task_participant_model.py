from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    UniqueConstraint,
    Uuid,
    inspect,
)

from app.models import Task, TaskParticipant, User


def test_task_participant_columns_and_primary_key_contract() -> None:
    table = TaskParticipant.__table__

    assert table.name == "task_participants"
    assert set(table.columns.keys()) == {
        "participant_id",
        "task_id",
        "employee_no",
        "participant_role",
        "is_primary",
        "confirm_status",
        "confirmed_at",
    }
    assert [column.name for column in table.primary_key.columns] == [
        "participant_id"
    ]
    assert isinstance(table.c.participant_id.type, Uuid)
    assert table.c.participant_id.default is not None
    assert table.c.participant_id.default.is_callable
    assert "id" not in table.columns
    assert "user_id" not in table.columns
    assert "employee_id" not in table.columns


def test_task_participant_foreign_keys_and_nullability() -> None:
    table = TaskParticipant.__table__
    task_foreign_key = next(iter(table.c.task_id.foreign_keys))
    employee_foreign_key = next(iter(table.c.employee_no.foreign_keys))

    assert table.c.task_id.nullable is False
    assert task_foreign_key.target_fullname == "tasks.task_id"
    assert task_foreign_key.ondelete == "RESTRICT"
    assert table.c.employee_no.nullable is False
    assert employee_foreign_key.target_fullname == "users.employee_no"
    assert employee_foreign_key.ondelete == "RESTRICT"
    assert table.c.participant_role.nullable is False
    assert isinstance(table.c.is_primary.type, Boolean)
    assert table.c.is_primary.nullable is False
    assert table.c.is_primary.default.arg is False
    assert table.c.confirm_status.nullable is True
    assert isinstance(table.c.confirmed_at.type, DateTime)
    assert table.c.confirmed_at.type.timezone is True
    assert table.c.confirmed_at.nullable is True


def test_task_participant_constraints_and_partial_unique_index() -> None:
    table = TaskParticipant.__table__
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {index.name: index for index in table.indexes}
    primary_index = indexes["uq_task_participants_one_primary_assignee"]

    assert unique_constraints == {
        ("task_id", "employee_no", "participant_role")
    }
    assert check_constraints == {
        "ck_task_participants_primary_is_assignee": (
            "NOT is_primary OR participant_role = 'assignee'"
        )
    }
    assert primary_index.unique is True
    assert tuple(column.name for column in primary_index.columns) == ("task_id",)
    where_clause = str(primary_index.dialect_options["postgresql"]["where"])
    assert "participant_role = 'assignee'" in where_clause
    assert "is_primary IS TRUE" in where_clause
    assert tuple(
        column.name for column in indexes["ix_task_participants_employee_no"].columns
    ) == ("employee_no",)
    assert ("participant_id",) not in {
        tuple(column.name for column in index.columns) for index in table.indexes
    }


def test_task_participant_relationships_are_bidirectional_and_safe() -> None:
    relationships = inspect(TaskParticipant).relationships

    assert set(relationships.keys()) == {"employee", "task"}
    assert relationships.task.back_populates == "participants"
    assert relationships.task.mapper.class_ is Task
    assert relationships.task.uselist is False
    assert {column.name for column in relationships.task.local_columns} == {
        "task_id"
    }
    assert relationships.employee.back_populates == "task_participations"
    assert relationships.employee.mapper.class_ is User
    assert relationships.employee.uselist is False
    assert {column.name for column in relationships.employee.local_columns} == {
        "employee_no"
    }

    for relationship_name in ("task", "employee"):
        cascade = relationships[relationship_name].cascade
        assert "delete" not in cascade
        assert "delete-orphan" not in cascade
