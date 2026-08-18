import warnings

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, Uuid, inspect
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import configure_mappers

from app.models import TaskNode, TaskNodeParticipant, User


def test_task_node_participant_columns_and_primary_key_contract() -> None:
    table = TaskNodeParticipant.__table__

    assert table.name == "task_node_participants"
    assert set(table.columns.keys()) == {
        "node_participant_id",
        "task_id",
        "node_id",
        "employee_no",
        "participant_role",
    }
    assert [column.name for column in table.primary_key.columns] == [
        "node_participant_id"
    ]
    assert isinstance(table.c.node_participant_id.type, Uuid)
    assert table.c.node_participant_id.default is not None
    assert table.c.node_participant_id.default.is_callable
    for forbidden_field in (
        "id",
        "user_id",
        "employee_id",
        "can_update_progress",
        "can_submit_report",
        "created_at",
        "updated_at",
        "confirm_status",
    ):
        assert forbidden_field not in table.columns


def test_task_node_participant_foreign_keys_and_unique_constraint() -> None:
    table = TaskNodeParticipant.__table__
    task_foreign_key = next(
        foreign_key
        for foreign_key in table.c.task_id.foreign_keys
        if foreign_key.target_fullname == "tasks.task_id"
    )
    employee_foreign_key = next(iter(table.c.employee_no.foreign_keys))
    composite_foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and len(constraint.elements) == 2
    }
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert task_foreign_key.ondelete == "RESTRICT"
    assert employee_foreign_key.target_fullname == "users.employee_no"
    assert employee_foreign_key.ondelete == "RESTRICT"
    assert composite_foreign_keys == {
        (
            ("task_id", "node_id"),
            ("task_nodes.task_id", "task_nodes.node_id"),
            "RESTRICT",
        )
    }
    assert unique_constraints == {
        ("task_id", "node_id", "employee_no", "participant_role")
    }


def test_task_node_participant_indexes_have_no_owner_projection_index() -> None:
    table = TaskNodeParticipant.__table__
    indexes = {index.name: index for index in table.indexes}

    assert set(indexes) == {
        "ix_task_node_participants_employee_no",
        "ix_task_node_participants_node_id",
    }
    assert all(index.unique is False for index in indexes.values())


def test_task_node_participant_relationships_are_unambiguous_and_safe() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", SAWarning)
        configure_mappers()

    relationships = inspect(TaskNodeParticipant).relationships
    assert set(relationships.keys()) == {"employee", "node"}
    assert relationships.node.back_populates == "participants"
    assert relationships.node.mapper.class_ is TaskNode
    assert relationships.employee.back_populates == "task_node_participations"
    assert relationships.employee.mapper.class_ is User
    assert {column.name for column in relationships.node.local_columns} == {
        "node_id",
        "task_id",
    }
    for relationship in relationships:
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade
