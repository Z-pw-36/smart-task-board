from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.sql.schema import PrimaryKeyConstraint

from app.models import RefreshToken

MIGRATION_DIRECTORY = Path("alembic/versions")
REVISION = "f7b8c9d0e1f2"
DOWN_REVISION = "e6f1a2b3c4d5"
TABLE_NAME = "auth_refresh_tokens"


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
            }
        )

    def drop_index(self, name: str, *, table_name: str | None = None, **_kwargs: object) -> None:
        self.dropped_indexes.append((name, table_name))

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)


def _load_migration() -> ModuleType:
    path = next(MIGRATION_DIRECTORY.glob(f"{REVISION}_*.py"))
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    spec = importlib.util.spec_from_file_location("auth_refresh_token_migration", path)
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


def test_auth_refresh_revision_is_current_head() -> None:
    module = _load_migration()

    assert module.revision == REVISION
    assert module.down_revision == DOWN_REVISION
    assert module.branch_labels is None
    assert module.depends_on is None


def test_auth_refresh_upgrade_matches_model_metadata() -> None:
    module = _load_migration()
    recorder = OperationRecorder()
    module.op = recorder
    module.upgrade()

    assert recorder.created_tables == [TABLE_NAME]
    migration_table = recorder.metadata.tables[TABLE_NAME]
    model_table = RefreshToken.__table__
    assert tuple(migration_table.columns.keys()) == tuple(model_table.columns.keys())
    for column_name in model_table.columns.keys():
        migration_column = migration_table.c[column_name]
        model_column = model_table.c[column_name]
        assert type(migration_column.type) is type(model_column.type)
        assert migration_column.nullable is model_column.nullable
        assert migration_column.server_default is None
        if isinstance(model_column.type, sa.String):
            assert migration_column.type.length == model_column.type.length
        if isinstance(model_column.type, sa.DateTime):
            assert migration_column.type.timezone is model_column.type.timezone
    assert _constraint_signatures(migration_table) == _constraint_signatures(model_table)
    assert recorder.created_indexes == [
        {
            "name": "ix_auth_refresh_tokens_employee_status",
            "table_name": TABLE_NAME,
            "columns": ("employee_no", "status", "expires_at"),
            "unique": False,
            "postgresql_where": None,
        }
    ]


def test_auth_refresh_downgrade_removes_index_then_table() -> None:
    module = _load_migration()
    recorder = OperationRecorder()
    module.op = recorder
    module.downgrade()

    assert recorder.dropped_indexes == [
        ("ix_auth_refresh_tokens_employee_status", TABLE_NAME)
    ]
    assert recorder.dropped_tables == [TABLE_NAME]
