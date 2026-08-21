from sqlalchemy import Uuid, inspect

from app.db.base import Base
from app.models import Department, User


def test_metadata_contains_only_approved_business_tables() -> None:
    assert set(Base.metadata.tables) == {
        "ai_extraction_records",
        "auth_refresh_tokens",
        "departments",
        "employee_profiles",
        "notifications",
        "operation_logs",
        "performance_metrics",
        "reminder_rules",
        "system_parameters",
        "task_inputs",
        "task_archives",
        "task_change_requests",
        "task_completion_reviews",
        "task_conflicts",
        "task_node_dependencies",
        "task_node_participants",
        "task_nodes",
        "task_participants",
        "task_performance_matches",
        "task_priority_scores",
        "task_progress_reports",
        "task_status_logs",
        "task_issues",
        "tasks",
        "user_authorized_scopes",
        "users",
        "workload_snapshots",
    }
    assert Department.__table__.name == "departments"
    assert User.__table__.name == "users"
    assert "department" not in Base.metadata.tables
    assert "user" not in Base.metadata.tables
    assert "boards" not in Base.metadata.tables
    assert "workspaces" not in Base.metadata.tables
    assert "projects" not in Base.metadata.tables
    for table_name in (
        "boards",
        "workspaces",
        "projects",
        "attachments",
        "ai_conversations",
        "ai_conversation_messages",
    ):
        assert table_name not in Base.metadata.tables


def test_department_columns_and_primary_key_contract() -> None:
    table = Department.__table__

    assert set(table.columns.keys()) == {
        "department_id",
        "parent_department_id",
        "department_name",
        "department_type",
        "department_path",
        "status",
    }
    assert [column.name for column in table.primary_key.columns] == ["department_id"]
    assert "id" not in table.columns

    department_id = table.c.department_id
    assert isinstance(department_id.type, Uuid)
    assert department_id.nullable is False
    assert department_id.default is not None
    assert department_id.default.is_callable


def test_department_parent_foreign_key_and_nullability() -> None:
    parent_department_id = Department.__table__.c.parent_department_id
    foreign_key = next(iter(parent_department_id.foreign_keys))

    assert parent_department_id.nullable is True
    assert foreign_key.target_fullname == "departments.department_id"
    assert foreign_key.ondelete == "RESTRICT"


def test_department_relationships_are_bidirectional_and_safe() -> None:
    relationships = inspect(Department).relationships

    assert set(relationships.keys()) == {"parent", "children", "tasks", "users"}
    assert relationships.parent.back_populates == "children"
    assert relationships.parent.uselist is False
    assert {column.name for column in relationships.parent.remote_side} == {
        "department_id"
    }
    assert relationships.children.back_populates == "parent"
    assert relationships.children.uselist is True
    assert relationships.users.back_populates == "department"
    assert relationships.users.uselist is True
    assert relationships.tasks.back_populates == "department"
    assert relationships.tasks.uselist is True

    for relationship_name in ("parent", "children", "users", "tasks"):
        cascade = relationships[relationship_name].cascade
        assert "delete" not in cascade
        assert "delete-orphan" not in cascade


def test_department_indexes_are_non_redundant() -> None:
    indexed_columns = {
        tuple(column.name for column in index.columns)
        for index in Department.__table__.indexes
    }

    assert indexed_columns == {("parent_department_id",), ("status",)}
    assert ("department_id",) not in indexed_columns
