from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.unit_of_work import UnitOfWork
from app.models import Task, TaskIssue, TaskNode, TaskProgressReport, User
from app.services import (
    CreateTaskIssueCommand,
    OpenTaskIssueConflictError,
    ProgressReportService,
    SubmitProgressReportCommand,
    TaskIssueService,
    TaskNodeWorkflowService,
)
from app.services.progress_issue_query import ProgressIssueQueryService
from app.services.task_board_query import TaskBoardQueryService

pytestmark = pytest.mark.postgresql

EXPECTED_DATABASE = "smarttaskboard_core_test"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 46479
EXPECTED_REVISION = "576787492bd1"
EXPECTED_TABLES = {
    "ai_extraction_records",
    "departments",
    "task_inputs",
    "task_issues",
    "task_node_dependencies",
    "task_node_participants",
    "task_nodes",
    "task_participants",
    "task_progress_reports",
    "task_status_logs",
    "tasks",
    "users",
}
NOW = datetime(2026, 8, 19, 2, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def batch2_engine() -> Iterator[Engine]:
    if os.getenv("RUN_POSTGRESQL_INTEGRATION") != "1":
        pytest.skip("set RUN_POSTGRESQL_INTEGRATION=1 for explicit PostgreSQL tests")
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")
    parsed = make_url(database_url)
    if (
        parsed.drivername != "postgresql+psycopg"
        or parsed.host != EXPECTED_HOST
        or parsed.port != EXPECTED_PORT
        or parsed.database != EXPECTED_DATABASE
    ):
        pytest.fail("Batch 2 target is not the approved isolated database")
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c statement_timeout=5000 -c lock_timeout=1000"},
    )
    try:
        assert set(inspect(engine).get_table_names(schema="public")) - {
            "alembic_version"
        } == EXPECTED_TABLES
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalars().all() == [EXPECTED_REVISION]
        yield engine
    finally:
        engine.dispose()


def test_progress_issue_lifecycle_guards_and_rollback_cleanup(
    batch2_engine: Engine,
) -> None:
    with batch2_engine.connect() as connection:
        outer = connection.begin()
        factory = sessionmaker(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        creator = f"B2-C-{uuid4().hex[:12]}"
        assignee = f"B2-A-{uuid4().hex[:12]}"
        owner = f"B2-O-{uuid4().hex[:12]}"
        task_id, node_id = uuid4(), uuid4()
        with factory() as session:
            session.add_all(
                [
                    User(
                        employee_no=employee_no,
                        name=employee_no,
                        role_type="employee",
                        status="active",
                    )
                    for employee_no in (creator, assignee, owner)
                ]
            )
            session.add(
                Task(
                    task_id=task_id,
                    task_name="Batch 2 integration",
                    creator_employee_no=creator,
                    main_assignee_employee_no=assignee,
                    status="in_progress",
                    task_version=1,
                    report_cycle="weekly:WED@09:00",
                    accepted_at=datetime(2026, 8, 17, 1, 0, tzinfo=UTC),
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.add(
                TaskNode(
                    node_id=node_id,
                    task_id=task_id,
                    node_order=1,
                    node_name="Integration node",
                    owner_employee_no=assignee,
                    status="in_progress",
                    progress_percent=60,
                )
            )
            session.commit()

        def uow_factory() -> UnitOfWork:
            return UnitOfWork(factory)

        report_service = ProgressReportService(uow_factory, clock=lambda: NOW)
        issue_service = TaskIssueService(uow_factory, clock=lambda: NOW)
        node_service = TaskNodeWorkflowService(uow_factory, clock=lambda: NOW)

        root = report_service.submit(
            SubmitProgressReportCommand(
                task_id=task_id,
                reporter_employee_no=assignee,
                expected_task_version=1,
                operation_source="postgresql-test",
                progress_percent=60,
                report_content="Root report",
            )
        )
        correction = report_service.submit(
            SubmitProgressReportCommand(
                task_id=task_id,
                reporter_employee_no=assignee,
                expected_task_version=2,
                operation_source="postgresql-test",
                progress_percent=65,
                report_content="Corrected report",
                corrects_report_id=root.progress_report_id,
            )
        )
        assert correction.corrects_report_id == root.progress_report_id
        assert correction.report_period_end is None

        issue = issue_service.create(
            CreateTaskIssueCommand(
                task_id=task_id,
                node_id=node_id,
                reported_by_employee_no=assignee,
                expected_task_version=3,
                operation_source="postgresql-test",
                issue_type="blocker",
                title="Blocked",
                description="Waiting for access",
                severity="high",
                owner_employee_no=owner,
            )
        )
        with factory() as session:
            board = TaskBoardQueryService(session, clock=lambda: NOW)
            issue_query = ProgressIssueQueryService(session, clock=lambda: NOW)
            owner_actions = board.available_actions(task_id, owner)
            owner_inbox = board.list_inbox(
                owner,
                action_code="handle_issue",
                limit=20,
                offset=0,
            )
            assert owner_actions["allowed_actions"] == []
            assert owner_inbox["total"] == 1
            assert owner_inbox["items"][0]["allowed_actions"] == [
                "start_processing_issue",
                "resolve_issue",
                "reject_issue",
            ]
            assert issue_query.get_issue(task_id, issue.issue_id, owner)[
                "issue_id"
            ] == issue.issue_id
        with pytest.raises(OpenTaskIssueConflictError):
            node_service.complete_node(
                task_id,
                node_id,
                assignee,
                4,
                "postgresql-test",
            )

        issue_service.transition(
            task_id,
            issue.issue_id,
            owner,
            4,
            "postgresql-test",
            "resolved",
            "Access granted",
        )
        with factory() as session:
            reporter_inbox = TaskBoardQueryService(
                session,
                clock=lambda: NOW,
            ).list_inbox(
                assignee,
                action_code="handle_issue",
                limit=20,
                offset=0,
            )
            assert reporter_inbox["total"] == 1
            assert reporter_inbox["items"][0]["allowed_actions"] == ["close_issue"]
        issue_service.transition(
            task_id,
            issue.issue_id,
            assignee,
            5,
            "postgresql-test",
            "closed",
            "Verified",
        )
        node_service.complete_node(
            task_id,
            node_id,
            assignee,
            6,
            "postgresql-test",
        )

        with factory() as session:
            reports = session.scalars(
                select(TaskProgressReport).where(TaskProgressReport.task_id == task_id)
            ).all()
            saved_issue = session.get(TaskIssue, issue.issue_id)
            saved_node = session.get(TaskNode, node_id)
            assert len(reports) == 2
            assert saved_issue is not None and saved_issue.status == "closed"
            assert saved_node is not None and saved_node.status == "completed"

        outer.rollback()

    with Session(batch2_engine) as verification:
        assert verification.scalar(
            select(func.count()).select_from(Task).where(Task.task_id == task_id)
        ) == 0
