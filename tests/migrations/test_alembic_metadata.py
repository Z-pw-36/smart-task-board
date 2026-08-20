import ast
import runpy
from contextlib import nullcontext
from pathlib import Path

from alembic.config import Config
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.sql.schema import PrimaryKeyConstraint

from alembic import context
from app.db.base import NAMING_CONVENTION, Base

EXPECTED_TABLES = {
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


def test_alembic_environment_loads_complete_metadata_without_database(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    config = Config()

    monkeypatch.setattr(context, "config", config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(
        context,
        "configure",
        lambda **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", lambda: None)

    runpy.run_path("alembic/env.py", run_name="alembic_test_env")

    target_metadata = captured["target_metadata"]
    assert target_metadata is Base.metadata
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_alembic_environment_explicitly_imports_model_registry() -> None:
    source = Path("alembic/env.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "app.models" in imported_modules


def test_base_has_complete_stable_naming_convention() -> None:
    assert dict(Base.metadata.naming_convention) == NAMING_CONVENTION
    assert set(NAMING_CONVENTION) == {"ck", "fk", "ix", "pk", "uq"}

    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            if isinstance(
                constraint,
                (
                    CheckConstraint,
                    ForeignKeyConstraint,
                    PrimaryKeyConstraint,
                    UniqueConstraint,
                ),
            ):
                assert constraint.name
        for index in table.indexes:
            assert index.name


def test_base_module_does_not_import_business_models() -> None:
    source = Path("app/db/base.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from_modules = {
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "app.models" not in imported_modules
    assert all(not module_name.startswith("app.models") for module_name in imported_from_modules)
