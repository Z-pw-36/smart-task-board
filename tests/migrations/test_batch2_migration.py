import importlib.util
import re
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.sql.schema import PrimaryKeyConstraint

import app.models  # noqa: F401
from app.db.base import Base

MIGRATION_DIRECTORY = Path("alembic/versions")
INITIAL_REVISION = "17f69ea12754"
BATCH2_REVISION = "576787492bd1"
NEW_TABLES = ("task_progress_reports", "task_issues")


class OperationRecorder:
    def __init__(self) -> None:
        self.metadata = sa.MetaData()
        self.operations: list[tuple[str, object]] = []
        self.created_tables: list[str] = []
        self.created_indexes: list[dict[str, object]] = []
        self.dropped_indexes: list[tuple[str, str | None]] = []
        self.dropped_tables: list[str] = []
        self.created_checks: list[tuple[str, str, str]] = []
        self.dropped_constraints: list[tuple[str, str, str | None]] = []
        self.executed_sql: list[str] = []

    def f(self, name: str) -> str:
        return name

    def execute(self, statement: object) -> None:
        sql = str(statement)
        self.executed_sql.append(sql)
        self.operations.append(("execute", sql))

    def create_check_constraint(
        self,
        name: str,
        table_name: str,
        condition: str,
    ) -> None:
        self.created_checks.append((name, table_name, condition))
        self.operations.append(("create_check_constraint", name))

    def drop_constraint(
        self,
        name: str,
        table_name: str,
        *,
        type_: str | None = None,
    ) -> None:
        self.dropped_constraints.append((name, table_name, type_))
        self.operations.append(("drop_constraint", name))

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
        **kwargs: object,
    ) -> None:
        self.dropped_indexes.append((name, table_name))
        self.operations.append(("drop_index", name))

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)
        self.operations.append(("drop_table", name))


def _normalized(value: object) -> str:
    return " ".join(str(value).split())


def _load_batch2_migration() -> ModuleType:
    matches = list(MIGRATION_DIRECTORY.glob(f"{BATCH2_REVISION}_*.py"))
    assert len(matches) == 1
    path = matches[0]
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    spec = importlib.util.spec_from_file_location("test_batch2_migration", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record_upgrade() -> tuple[ModuleType, OperationRecorder]:
    module = _load_batch2_migration()
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


def _index_signatures_from_model() -> set[tuple[object, ...]]:
    signatures: set[tuple[object, ...]] = set()
    for table_name in NEW_TABLES:
        table = Base.metadata.tables[table_name]
        for index in table.indexes:
            where = index.dialect_options["postgresql"].get("where")
            signatures.add(
                (
                    table_name,
                    str(index.name),
                    tuple(column.name for column in index.columns),
                    bool(index.unique),
                    _normalized(where) if where is not None else None,
                )
            )
    return signatures


def _index_signatures_from_migration(
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


def test_batch2_revision_forms_one_linear_chain() -> None:
    module = _load_batch2_migration()

    assert module.revision == BATCH2_REVISION
    assert module.down_revision == INITIAL_REVISION
    assert module.branch_labels is None
    assert module.depends_on is None


def test_batch2_upgrade_preflights_report_cycle_before_schema_changes() -> None:
    _, recorder = _record_upgrade()

    assert len(recorder.executed_sql) == 1
    preflight = _normalized(recorder.executed_sql[0])
    assert "FROM tasks" in preflight
    assert "report_cycle IS NOT NULL" in preflight
    assert "report_cycle !~" in preflight
    assert "weekly:" in preflight
    assert "MON|TUE|WED|THU|FRI|SAT|SUN" in preflight
    assert "RAISE EXCEPTION" in preflight
    assert "UPDATE" not in preflight.upper()
    assert "DELETE" not in preflight.upper()
    assert recorder.operations[:4] == [
        ("execute", recorder.executed_sql[0]),
        ("create_check_constraint", "ck_tasks_report_cycle_format"),
        ("create_table", "task_progress_reports"),
        ("create_index", "ix_task_progress_reports_corrects_report_id"),
    ]
    assert recorder.created_checks == [
        (
            "ck_tasks_report_cycle_format",
            "tasks",
            "report_cycle IS NULL OR report_cycle ~ "
            "'^weekly:(MON|TUE|WED|THU|FRI|SAT|SUN)@"
            "([01][0-9]|2[0-3]):[0-5][0-9]$'",
        )
    ]


def test_report_cycle_pattern_accepts_only_frozen_weekly_format() -> None:
    module = _load_batch2_migration()
    valid_values = {
        "weekly:MON@00:00",
        "weekly:TUE@09:30",
        "weekly:WED@12:05",
        "weekly:THU@18:45",
        "weekly:FRI@23:59",
        "weekly:SAT@08:00",
        "weekly:SUN@20:10",
    }
    invalid_values = {
        "",
        "daily:MON@09:30",
        "weekly:mon@09:30",
        "weekly:MON@9:30",
        "weekly:MON@24:00",
        "weekly:MON@23:60",
        " weekly:MON@09:30",
        "weekly:MON@09:30 ",
    }

    assert all(re.fullmatch(module.REPORT_CYCLE_PATTERN, value) for value in valid_values)
    assert all(
        re.fullmatch(module.REPORT_CYCLE_PATTERN, value) is None
        for value in invalid_values
    )


def test_batch2_migration_tables_match_model_metadata() -> None:
    _, recorder = _record_upgrade()

    assert tuple(recorder.created_tables) == NEW_TABLES
    assert set(recorder.metadata.tables) == set(NEW_TABLES)
    for table_name in NEW_TABLES:
        migration_table = recorder.metadata.tables[table_name]
        model_table = Base.metadata.tables[table_name]
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


def test_batch2_migration_indexes_match_models_and_partial_predicates() -> None:
    _, recorder = _record_upgrade()

    assert _index_signatures_from_migration(recorder) == (
        _index_signatures_from_model()
    )
    progress_partial = next(
        item
        for item in recorder.created_indexes
        if item["name"] == "uq_task_progress_reports_one_current_task_period"
    )
    assert progress_partial["unique"] is True
    progress_where = _normalized(progress_partial["postgresql_where"])
    assert "node_id IS NULL" in progress_where
    assert "corrects_report_id IS NULL" in progress_where
    assert "report_period_end IS NOT NULL" in progress_where
    issue_partial = next(
        item
        for item in recorder.created_indexes
        if item["name"] == "ix_task_issues_active_task_node"
    )
    assert issue_partial["unique"] is False
    assert "status IN ('open', 'processing')" in _normalized(
        issue_partial["postgresql_where"]
    )


def test_batch2_downgrade_reverses_tables_then_task_check() -> None:
    module = _load_batch2_migration()
    recorder = OperationRecorder()
    module.op = recorder

    module.downgrade()

    assert recorder.dropped_tables == ["task_issues", "task_progress_reports"]
    assert recorder.dropped_constraints == [
        ("ck_tasks_report_cycle_format", "tasks", "check")
    ]
    issue_drop_position = recorder.operations.index(("drop_table", "task_issues"))
    report_drop_position = recorder.operations.index(
        ("drop_table", "task_progress_reports")
    )
    check_drop_position = recorder.operations.index(
        ("drop_constraint", "ck_tasks_report_cycle_format")
    )
    assert issue_drop_position < report_drop_position < check_drop_position


def test_batch2_static_upgrade_downgrade_reupgrade_is_deterministic() -> None:
    module = _load_batch2_migration()
    first_upgrade = OperationRecorder()
    module.op = first_upgrade
    module.upgrade()

    downgrade = OperationRecorder()
    module.op = downgrade
    module.downgrade()

    second_upgrade = OperationRecorder()
    module.op = second_upgrade
    module.upgrade()

    assert first_upgrade.created_tables == list(NEW_TABLES)
    assert downgrade.dropped_tables == list(reversed(NEW_TABLES))
    assert second_upgrade.created_tables == first_upgrade.created_tables
    assert second_upgrade.created_checks == first_upgrade.created_checks
    assert _index_signatures_from_migration(second_upgrade) == (
        _index_signatures_from_migration(first_upgrade)
    )
    for table_name in NEW_TABLES:
        assert _constraint_signatures(
            second_upgrade.metadata.tables[table_name]
        ) == _constraint_signatures(first_upgrade.metadata.tables[table_name])
