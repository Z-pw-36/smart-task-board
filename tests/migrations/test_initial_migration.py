import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.sql.schema import PrimaryKeyConstraint

import app.models  # noqa: F401
from app.db.base import Base

MIGRATION_DIRECTORY = Path("alembic/versions")
EXPECTED_CREATE_ORDER = (
    "departments",
    "users",
    "task_inputs",
    "tasks",
    "ai_extraction_records",
    "task_nodes",
    "task_participants",
    "task_status_logs",
    "task_node_dependencies",
    "task_node_participants",
)
EXPECTED_TABLES = set(EXPECTED_CREATE_ORDER)
EXPECTED_DROP_ORDER = tuple(reversed(EXPECTED_CREATE_ORDER))
FORBIDDEN_TABLES = {
    "boards",
    "notifications",
    "operation_logs",
    "outbox",
    "performance_records",
    "task_issues",
    "workspaces",
}


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
        **kwargs: object,
    ) -> None:
        self.dropped_indexes.append((name, table_name))

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)


def _migration_files() -> list[Path]:
    return sorted(MIGRATION_DIRECTORY.glob("*.py"))


def _load_migration(path: Path) -> ModuleType:
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    spec = importlib.util.spec_from_file_location(f"test_migration_{path.stem}", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record_migration() -> tuple[ModuleType, OperationRecorder]:
    module = _load_migration(_migration_files()[0])
    recorder = OperationRecorder()
    module.op = recorder
    module.upgrade()
    module.downgrade()
    return module, recorder


def _normalize_sql(value: object) -> str:
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
            signatures.add(
                ("ck", str(constraint.name), _normalize_sql(constraint.sqltext))
            )
        elif isinstance(constraint, ForeignKeyConstraint):
            targets = tuple(element.target_fullname for element in constraint.elements)
            signatures.add(
                (
                    "fk",
                    str(constraint.name),
                    columns,
                    targets,
                    constraint.ondelete,
                )
            )
    return signatures


def _model_index_signatures() -> set[tuple[object, ...]]:
    signatures: set[tuple[object, ...]] = set()
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            where = index.dialect_options["postgresql"].get("where")
            signatures.add(
                (
                    table.name,
                    str(index.name),
                    tuple(column.name for column in index.columns),
                    bool(index.unique),
                    _normalize_sql(where) if where is not None else None,
                )
            )
    return signatures


def _migration_index_signatures(
    recorder: OperationRecorder,
) -> set[tuple[object, ...]]:
    return {
        (
            item["table_name"],
            item["name"],
            item["columns"],
            item["unique"],
            _normalize_sql(item["postgresql_where"])
            if item["postgresql_where"] is not None
            else None,
        )
        for item in recorder.created_indexes
    }


def test_initial_migration_is_the_only_importable_root_revision() -> None:
    files = _migration_files()

    assert len(files) == 1
    module = _load_migration(files[0])
    assert module.revision
    assert module.down_revision is None
    assert module.branch_labels is None
    assert module.depends_on is None
    assert callable(module.upgrade)
    assert callable(module.downgrade)


def test_initial_migration_creates_and_drops_exact_tables_in_safe_order() -> None:
    _, recorder = _record_migration()

    assert tuple(recorder.created_tables) == EXPECTED_CREATE_ORDER
    assert set(recorder.metadata.tables) == EXPECTED_TABLES
    assert FORBIDDEN_TABLES.isdisjoint(recorder.metadata.tables)
    assert tuple(recorder.dropped_tables) == EXPECTED_DROP_ORDER


def test_initial_migration_columns_match_model_metadata_without_server_defaults() -> None:
    _, recorder = _record_migration()

    for table_name in EXPECTED_TABLES:
        migration_table = recorder.metadata.tables[table_name]
        model_table = Base.metadata.tables[table_name]
        assert tuple(migration_table.columns.keys()) == tuple(model_table.columns.keys())
        for column_name in model_table.columns.keys():
            migration_column = migration_table.c[column_name]
            model_column = model_table.c[column_name]
            assert type(migration_column.type) is type(model_column.type)
            assert migration_column.nullable is model_column.nullable
            assert migration_column.server_default is None
            if isinstance(model_column.type, sa.DateTime):
                assert migration_column.type.timezone is model_column.type.timezone
            if isinstance(model_column.type, sa.Numeric):
                assert migration_column.type.precision == model_column.type.precision
                assert migration_column.type.scale == model_column.type.scale


def test_initial_migration_constraints_match_model_metadata() -> None:
    _, recorder = _record_migration()

    for table_name in EXPECTED_TABLES:
        assert _constraint_signatures(recorder.metadata.tables[table_name]) == (
            _constraint_signatures(Base.metadata.tables[table_name])
        )

    dependencies = recorder.metadata.tables["task_node_dependencies"]
    dependency_foreign_keys = {
        (
            tuple(column.name for column in constraint.columns),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in dependencies.foreign_key_constraints
        if len(constraint.elements) == 2
    }
    assert dependency_foreign_keys == {
        (
            ("task_id", "predecessor_node_id"),
            ("task_nodes.task_id", "task_nodes.node_id"),
        ),
        (
            ("task_id", "successor_node_id"),
            ("task_nodes.task_id", "task_nodes.node_id"),
        ),
    }


def test_initial_migration_indexes_match_models_and_keep_partial_unique_index() -> None:
    _, recorder = _record_migration()

    assert _migration_index_signatures(recorder) == _model_index_signatures()
    partial_index = next(
        item
        for item in recorder.created_indexes
        if item["name"] == "uq_task_participants_one_primary_assignee"
    )
    assert partial_index["unique"] is True
    where = _normalize_sql(partial_index["postgresql_where"])
    assert "participant_role = 'assignee'" in where
    assert "is_primary IS TRUE" in where
