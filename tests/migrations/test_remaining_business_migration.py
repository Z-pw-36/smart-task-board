from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.sql.schema import PrimaryKeyConstraint

from app.models import (
    EmployeeProfile,
    Notification,
    OperationLog,
    PerformanceMetric,
    ReminderRule,
    SystemParameter,
    TaskArchive,
    TaskConflict,
    TaskPerformanceMatch,
    TaskPriorityScore,
    UserAuthorizedScope,
    WorkloadSnapshot,
)

MIGRATION_DIRECTORY = Path("alembic/versions")
REVISION = "e6f1a2b3c4d5"
DOWN_REVISION = "d4a8e53b7c19"
NEW_MODELS = (
    EmployeeProfile,
    PerformanceMetric,
    TaskPerformanceMatch,
    WorkloadSnapshot,
    TaskPriorityScore,
    TaskConflict,
    ReminderRule,
    Notification,
    TaskArchive,
    OperationLog,
    UserAuthorizedScope,
    SystemParameter,
)
EXPECTED_DEFAULT_PARAMETER_KEYS = {
    "daily_capacity_hours",
    "standard_task_count",
    "standard_task_weight",
    "emergency_tolerance_count",
    "importance_threshold",
    "urgency_threshold",
}


class OperationRecorder:
    def __init__(self) -> None:
        self.metadata = sa.MetaData()
        self.created_tables: list[str] = []
        self.created_indexes: list[dict[str, object]] = []
        self.dropped_indexes: list[tuple[str, str | None]] = []
        self.dropped_tables: list[str] = []
        self.bulk_inserted: list[tuple[str, list[dict[str, object]]]] = []

    def f(self, name: str) -> str:
        return name

    def create_table(self, name: str, *elements: object) -> None:
        sa.Table(name, self.metadata, *elements)
        self.created_tables.append(name)

    def create_index(
        self,
        name: str,
        table_name: str,
        columns: list[str],
        *,
        unique: bool = False,
        **kwargs: object,
    ) -> None:
        self.created_indexes.append(
            {
                "name": name,
                "table_name": table_name,
                "columns": tuple(columns),
                "unique": unique,
                "postgresql_where": kwargs.get("postgresql_where"),
                "postgresql_using": kwargs.get("postgresql_using"),
            }
        )

    def drop_index(self, name: str, *, table_name: str | None = None, **_kwargs: object) -> None:
        self.dropped_indexes.append((name, table_name))

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)

    def bulk_insert(self, table: sa.Table, rows: list[dict[str, object]]) -> None:
        self.bulk_inserted.append((table.name, rows))


def _load_migration() -> ModuleType:
    path = next(MIGRATION_DIRECTORY.glob(f"{REVISION}_*.py"))
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    spec = importlib.util.spec_from_file_location("remaining_business_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalized(value: object) -> str:
    return " ".join(str(value).split())


def _constraint_signatures(table: sa.Table) -> set[tuple[object, ...]]:
    signatures: set[tuple[object, ...]] = set()
    for constraint in table.constraints:
        columns = tuple(column.name for column in constraint.columns)
        if isinstance(constraint, PrimaryKeyConstraint):
            signatures.add(("pk", str(constraint.name), columns))
        elif isinstance(constraint, UniqueConstraint):
            signatures.add(("uq", str(constraint.name), columns))
        elif isinstance(constraint, CheckConstraint):
            signatures.add(("ck", str(constraint.name), _normalized(constraint.sqltext)))
        elif isinstance(constraint, ForeignKeyConstraint):
            signatures.add(
                (
                    "fk",
                    str(constraint.name),
                    columns,
                    tuple(element.target_fullname for element in constraint.elements),
                    constraint.ondelete,
                )
            )
    return signatures


def _index_signatures(table: sa.Table) -> set[tuple[object, ...]]:
    signatures: set[tuple[object, ...]] = set()
    for index in table.indexes:
        using = index.dialect_options["postgresql"].get("using") or None
        where = index.dialect_options["postgresql"].get("where")
        signatures.add(
            (
                table.name,
                str(index.name),
                tuple(column.name for column in index.columns),
                bool(index.unique),
                _normalized(where) if where is not None else None,
                using,
            )
        )
    return signatures


def _migration_index_signatures(recorder: OperationRecorder) -> set[tuple[object, ...]]:
    return {
        (
            item["table_name"],
            item["name"],
            item["columns"],
            item["unique"],
            _normalized(item["postgresql_where"])
            if item["postgresql_where"] is not None
            else None,
            item["postgresql_using"],
        )
        for item in recorder.created_indexes
    }


def test_remaining_business_revision_extends_change_request_head() -> None:
    module = _load_migration()

    assert module.revision == REVISION
    assert module.down_revision == DOWN_REVISION
    assert module.branch_labels is None
    assert module.depends_on is None


def test_remaining_business_upgrade_matches_model_metadata_and_seeded_parameters() -> None:
    module = _load_migration()
    recorder = OperationRecorder()
    module.op = recorder
    module.upgrade()

    expected_tables = tuple(model.__table__.name for model in NEW_MODELS)
    assert tuple(recorder.created_tables) == expected_tables
    assert set(recorder.metadata.tables) == set(expected_tables)
    for model in NEW_MODELS:
        migration_table = recorder.metadata.tables[model.__table__.name]
        model_table = model.__table__
        assert tuple(migration_table.columns.keys()) == tuple(model_table.columns.keys())
        for column_name in model_table.columns.keys():
            migration_column = migration_table.c[column_name]
            model_column = model_table.c[column_name]
            assert type(migration_column.type) is type(model_column.type)
            assert migration_column.nullable is model_column.nullable
            assert migration_column.server_default is None
            if isinstance(model_column.type, sa.DateTime):
                assert migration_column.type.timezone is model_column.type.timezone
        assert _constraint_signatures(migration_table) == _constraint_signatures(model_table)

    model_indexes = set().union(*(_index_signatures(model.__table__) for model in NEW_MODELS))
    assert _migration_index_signatures(recorder) == model_indexes
    assert len(recorder.bulk_inserted) == 1
    table_name, rows = recorder.bulk_inserted[0]
    assert table_name == "system_parameters"
    assert {row["param_key"] for row in rows} == EXPECTED_DEFAULT_PARAMETER_KEYS


def test_remaining_business_downgrade_removes_new_indexes_before_tables() -> None:
    module = _load_migration()
    recorder = OperationRecorder()
    module.op = recorder
    module.downgrade()

    assert tuple(recorder.dropped_tables) == tuple(
        reversed([model.__table__.name for model in NEW_MODELS])
    )
    dropped_index_tables = {table for _name, table in recorder.dropped_indexes}
    assert dropped_index_tables <= {model.__table__.name for model in NEW_MODELS}
