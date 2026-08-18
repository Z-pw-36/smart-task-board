import warnings

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    inspect,
)
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import configure_mappers

from app.models import Task, TaskNode, TaskNodeDependency


def test_task_node_dependency_columns_and_primary_key_contract() -> None:
    table = TaskNodeDependency.__table__

    assert table.name == "task_node_dependencies"
    assert set(table.columns.keys()) == {
        "dependency_id",
        "task_id",
        "predecessor_node_id",
        "successor_node_id",
        "dependency_type",
    }
    assert [column.name for column in table.primary_key.columns] == [
        "dependency_id"
    ]
    assert isinstance(table.c.dependency_id.type, Uuid)
    assert table.c.dependency_id.default is not None
    assert table.c.dependency_id.default.is_callable
    assert "id" not in table.columns


def test_task_node_dependency_foreign_keys_enforce_same_task() -> None:
    table = TaskNodeDependency.__table__
    task_foreign_key = next(
        foreign_key
        for foreign_key in table.c.task_id.foreign_keys
        if foreign_key.target_fullname == "tasks.task_id"
    )
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

    assert task_foreign_key.ondelete == "RESTRICT"
    assert composite_foreign_keys == {
        (
            ("task_id", "predecessor_node_id"),
            ("task_nodes.task_id", "task_nodes.node_id"),
            "RESTRICT",
        ),
        (
            ("task_id", "successor_node_id"),
            ("task_nodes.task_id", "task_nodes.node_id"),
            "RESTRICT",
        ),
    }


def test_task_node_dependency_defaults_constraints_and_indexes() -> None:
    table = TaskNodeDependency.__table__
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexed_columns = {
        tuple(column.name for column in index.columns) for index in table.indexes
    }

    assert isinstance(table.c.dependency_type.type, String)
    assert table.c.dependency_type.default.arg == "finish_to_start"
    assert unique_constraints == {
        ("predecessor_node_id", "successor_node_id", "dependency_type")
    }
    assert checks == {
        "ck_task_node_dependencies_not_self": (
            "predecessor_node_id <> successor_node_id"
        )
    }
    assert indexed_columns == {("successor_node_id",), ("task_id",)}


def test_task_node_dependency_relationships_are_unambiguous_and_safe() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", SAWarning)
        configure_mappers()

    relationships = inspect(TaskNodeDependency).relationships
    assert set(relationships.keys()) == {
        "predecessor_node",
        "successor_node",
        "task",
    }
    assert relationships.task.back_populates == "node_dependencies"
    assert relationships.task.mapper.class_ is Task
    assert relationships.predecessor_node.back_populates == "outgoing_dependencies"
    assert relationships.predecessor_node.mapper.class_ is TaskNode
    assert relationships.successor_node.back_populates == "incoming_dependencies"
    assert relationships.successor_node.mapper.class_ is TaskNode
    assert {column.name for column in relationships.predecessor_node.local_columns} == {
        "predecessor_node_id",
        "task_id",
    }
    assert {column.name for column in relationships.successor_node.local_columns} == {
        "successor_node_id",
        "task_id",
    }
    for relationship in relationships:
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade
