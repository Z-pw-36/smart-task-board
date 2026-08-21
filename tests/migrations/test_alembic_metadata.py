import ast
import runpy
from contextlib import nullcontext
from pathlib import Path

from alembic.config import Config
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.sql.schema import PrimaryKeyConstraint

from alembic import context
from app.core.config import get_settings
from app.db.base import NAMING_CONVENTION, Base

EXPECTED_TABLES = {
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


def test_alembic_online_engine_uses_configured_connect_timeout(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    config = Config()

    class FakeConnectable:
        def connect(self):
            return nullcontext(object())

    def fake_engine_from_config(*_args, **kwargs):
        captured.update(kwargs)
        return FakeConnectable()

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://test:test@127.0.0.1:46479/smarttaskboard_core_test",
    )
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "2")
    get_settings.cache_clear()
    monkeypatch.setattr(context, "config", config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(context, "configure", lambda **_kwargs: None)
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", lambda: None)
    monkeypatch.setattr("sqlalchemy.engine_from_config", fake_engine_from_config)

    runpy.run_path("alembic/env.py", run_name="alembic_online_test_env")

    assert captured["connect_args"] == {"connect_timeout": 2}
    get_settings.cache_clear()


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
