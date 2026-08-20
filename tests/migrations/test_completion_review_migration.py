import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.sql.schema import PrimaryKeyConstraint

import app.models  # noqa: F401
from app.db.base import Base

MIGRATION_DIRECTORY = Path("alembic/versions")
PREVIOUS_REVISION = "576787492bd1"
COMPLETION_REVIEW_REVISION = "c31f8e7a4d02"
TABLE_NAME = "task_completion_reviews"


class OperationRecorder:
    def __init__(self) -> None:
        self.metadata = sa.MetaData()
        self.operations: list[tuple[str, object]] = []
        self.executed_sql: list[str] = []
        self.created_tables: list[str] = []
        self.created_indexes: list[dict[str, object]] = []
        self.dropped_indexes: list[tuple[str, str | None]] = []
        self.dropped_tables: list[str] = []

    def f(self, name: str) -> str:
        return name

    def execute(self, statement: object) -> None:
        sql = str(statement)
        self.executed_sql.append(sql)
        self.operations.append(("execute", sql))

    def create_table(self, name: str, *elements: object) -> None:
        sa.Table(name, self.metadata, *elements)
        self.created_tables.append(name)
        self.operations.append(("create_table", name))

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
        self.operations.append(("create_index", name))

    def drop_index(
        self,
        name: str,
        *,
        table_name: str | None = None,
        **_kwargs: object,
    ) -> None:
        self.dropped_indexes.append((name, table_name))
        self.operations.append(("drop_index", name))

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)
        self.operations.append(("drop_table", name))


def _normalized(value: object) -> str:
    return " ".join(str(value).split())


def _load_migration() -> ModuleType:
    matches = list(
        MIGRATION_DIRECTORY.glob(f"{COMPLETION_REVIEW_REVISION}_*.py")
    )
    assert len(matches) == 1
    path = matches[0]
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    spec = importlib.util.spec_from_file_location(
        "test_completion_review_migration_module",
        path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record_upgrade() -> tuple[ModuleType, OperationRecorder]:
    module = _load_migration()
    recorder = OperationRecorder()
    module.op = recorder
    module.upgrade()
    return module, recorder


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
                ("ck", str(constraint.name), _normalized(constraint.sqltext))
            )
        elif isinstance(constraint, ForeignKeyConstraint):
            targets = tuple(
                element.target_fullname for element in constraint.elements
            )
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
    table = Base.metadata.tables[TABLE_NAME]
    for index in table.indexes:
        where = index.dialect_options["postgresql"].get("where")
        signatures.add(
            (
                TABLE_NAME,
                str(index.name),
                tuple(column.name for column in index.columns),
                bool(index.unique),
                _normalized(where) if where is not None else None,
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
            _normalized(item["postgresql_where"])
            if item["postgresql_where"] is not None
            else None,
        )
        for item in recorder.created_indexes
    }


def test_completion_review_revision_extends_current_head_linearly() -> None:
    module = _load_migration()

    assert module.revision == COMPLETION_REVIEW_REVISION
    assert module.down_revision == PREVIOUS_REVISION
    assert module.branch_labels is None
    assert module.depends_on is None


def test_upgrade_preflights_then_creates_schema_then_backfills() -> None:
    _, recorder = _record_upgrade()

    assert len(recorder.executed_sql) == 2
    preflight = _normalized(recorder.executed_sql[0])
    backfill = _normalized(recorder.executed_sql[1])
    assert "pending_review/completed task lacks completion submission" in preflight
    assert "completion history contains a null required actor" in preflight
    assert "multiple unresolved completion submissions" in preflight
    assert "completion history contains a stale unresolved submission" in preflight
    assert "latest completion decision conflicts with task status" in preflight
    assert "INSERT INTO" not in preflight.upper()
    assert "INSERT INTO task_completion_reviews" in backfill
    assert "completion_note" in backfill
    assert "deliverable_summary" in backfill
    assert "NULL, NULL" in backfill
    assert "is_legacy_import" in backfill
    assert "true" in backfill
    assert "row_number()" in backfill
    assert "completion_submitted" in backfill
    assert "completion_approved" in backfill

    create_position = recorder.operations.index(
        ("create_table", TABLE_NAME)
    )
    assert recorder.operations[0][0] == "execute"
    assert recorder.operations[-1][0] == "execute"
    assert 0 < create_position < len(recorder.operations) - 1


def test_migration_table_matches_model_metadata_exactly() -> None:
    _, recorder = _record_upgrade()
    migration_table = recorder.metadata.tables[TABLE_NAME]
    model_table = Base.metadata.tables[TABLE_NAME]

    assert recorder.created_tables == [TABLE_NAME]
    assert tuple(migration_table.columns.keys()) == tuple(
        model_table.columns.keys()
    )
    for column_name in model_table.columns.keys():
        migration_column = migration_table.c[column_name]
        model_column = model_table.c[column_name]
        assert type(migration_column.type) is type(model_column.type)
        assert migration_column.nullable is model_column.nullable
        assert migration_column.server_default is None
        if isinstance(model_column.type, sa.DateTime):
            assert migration_column.type.timezone is model_column.type.timezone
    assert _constraint_signatures(migration_table) == _constraint_signatures(
        model_table
    )


def test_migration_indexes_match_model_and_partial_uniqueness() -> None:
    _, recorder = _record_upgrade()

    assert _migration_index_signatures(recorder) == _model_index_signatures()
    partial = next(
        item
        for item in recorder.created_indexes
        if item["name"]
        == "uq_task_completion_reviews_one_submitted_per_task"
    )
    assert partial["unique"] is True
    assert partial["columns"] == ("task_id",)
    assert "review_status = 'submitted'" in _normalized(
        partial["postgresql_where"]
    )


def test_downgrade_guards_history_then_removes_only_new_indexes_and_table() -> None:
    module = _load_migration()
    recorder = OperationRecorder()
    module.op = recorder

    module.downgrade()

    assert len(recorder.executed_sql) == 1
    assert (
        "cannot downgrade while completion review history exists"
        in _normalized(recorder.executed_sql[0])
    )
    assert recorder.operations[0][0] == "execute"
    assert recorder.dropped_tables == [TABLE_NAME]
    assert {name for name, table_name in recorder.dropped_indexes} == {
        "ix_task_completion_reviews_reviewer_status_timeline",
        "ix_task_completion_reviews_rework_node",
        "ix_task_completion_reviews_submitter_timeline",
        "ix_task_completion_reviews_task_timeline",
        "uq_task_completion_reviews_one_submitted_per_task",
    }
    assert all(
        table_name == TABLE_NAME
        for _, table_name in recorder.dropped_indexes
    )
    assert recorder.operations[-1] == ("drop_table", TABLE_NAME)
