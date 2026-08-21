import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKeyConstraint
from sqlalchemy.sql.schema import PrimaryKeyConstraint

from app.models import TaskChangeRequest

MIGRATION_DIRECTORY = Path("alembic/versions")
REVISION = "d4a8e53b7c19"
TABLE_NAME = "task_change_requests"


class OperationRecorder:
    def __init__(self) -> None:
        self.metadata = sa.MetaData()
        self.created_tables: list[str] = []
        self.created_indexes: list[dict[str, object]] = []
        self.dropped_indexes: list[tuple[str, str | None]] = []
        self.dropped_tables: list[str] = []

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
        unique: bool,
        **kwargs: object,
    ) -> None:
        self.created_indexes.append(
            {
                "name": name,
                "table_name": table_name,
                "columns": tuple(columns),
                "unique": unique,
                "postgresql_where": kwargs.get("postgresql_where"),
            }
        )

    def drop_index(
        self,
        name: str,
        *,
        table_name: str | None = None,
        **_kwargs: object,
    ) -> None:
        self.dropped_indexes.append((name, table_name))

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)


def _load_migration() -> ModuleType:
    path = next(MIGRATION_DIRECTORY.glob(f"{REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location("change_request_migration", path)
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


def _index_signatures_from_model() -> set[tuple[object, ...]]:
    table = TaskChangeRequest.__table__
    return {
        (
            str(index.name),
            tuple(column.name for column in index.columns),
            bool(index.unique),
            _normalized(index.dialect_options["postgresql"].get("where"))
            if index.dialect_options["postgresql"].get("where") is not None
            else None,
        )
        for index in table.indexes
    }


def test_revision_extends_completion_review_head() -> None:
    module = _load_migration()
    assert module.revision == REVISION
    assert module.down_revision == "c31f8e7a4d02"
    assert module.branch_labels is None
    assert module.depends_on is None


def test_upgrade_schema_matches_model_metadata() -> None:
    module = _load_migration()
    recorder = OperationRecorder()
    module.op = recorder
    module.upgrade()

    assert recorder.created_tables == [TABLE_NAME]
    migration_table = recorder.metadata.tables[TABLE_NAME]
    model_table = TaskChangeRequest.__table__
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
    migration_indexes = {
        (
            item["name"],
            item["columns"],
            item["unique"],
            _normalized(item["postgresql_where"])
            if item["postgresql_where"] is not None
            else None,
        )
        for item in recorder.created_indexes
    }
    assert migration_indexes == _index_signatures_from_model()


def test_downgrade_removes_indexes_then_table() -> None:
    module = _load_migration()
    recorder = OperationRecorder()
    module.op = recorder
    module.downgrade()
    assert recorder.dropped_tables == [TABLE_NAME]
    assert {name for name, table in recorder.dropped_indexes} == {
        "ix_task_change_requests_requester_timeline",
        "ix_task_change_requests_status_timeline",
        "ix_task_change_requests_task_status_timeline",
        "ix_task_change_requests_task_timeline",
        "uq_task_change_requests_one_pending_per_task",
    }
    assert all(table == TABLE_NAME for _, table in recorder.dropped_indexes)

