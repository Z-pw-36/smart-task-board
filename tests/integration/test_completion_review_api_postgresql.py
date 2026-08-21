from __future__ import annotations

import os
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, delete, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api import dependencies
from app.core.config import Settings, get_settings
from app.db.unit_of_work import UnitOfWork
from app.main import app
from app.models import (
    Department,
    OperationLog,
    Task,
    TaskCompletionReview,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskStatusLog,
    User,
)

pytestmark = pytest.mark.postgresql

EXPECTED_DATABASE = "smarttaskboard_core_test"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 46479
EXPECTED_REVISION = "f7b8c9d0e1f2"
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
    "task_archives",
    "task_completion_reviews",
    "task_conflicts",
    "task_change_requests",
    "task_inputs",
    "task_issues",
    "task_node_dependencies",
    "task_node_participants",
    "task_nodes",
    "task_participants",
    "task_progress_reports",
    "task_status_logs",
    "tasks",
    "task_performance_matches",
    "task_priority_scores",
    "user_authorized_scopes",
    "users",
    "workload_snapshots",
}


@dataclass(frozen=True)
class CompletionReferences:
    department_id: UUID
    creator: str
    assignee: str
    reviewer: str
    outsider: str

    @property
    def employee_nos(self) -> tuple[str, ...]:
        return (
            self.creator,
            self.assignee,
            self.reviewer,
            self.outsider,
        )


def _references() -> CompletionReferences:
    suffix = uuid4().hex[:12]
    return CompletionReferences(
        department_id=uuid4(),
        creator=f"W1-C-{suffix}",
        assignee=f"W1-A-{suffix}",
        reviewer=f"W1-R-{suffix}",
        outsider=f"W1-O-{suffix}",
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, employee_no: str) -> str:
    response = client.post(
        "/api/v1/auth/prototype-login",
        json={"employee_no": employee_no},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _post_action(
    client: TestClient,
    token: str,
    task_id: UUID,
    action: str,
    expected_task_version: int,
    **payload: object,
):
    return client.post(
        f"/api/v1/tasks/{task_id}/actions/{action}",
        headers=_bearer(token),
        json={"expected_task_version": expected_task_version, **payload},
    )


def _assert_error(response, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code


def _create_ready_task(
    client: TestClient,
    refs: CompletionReferences,
    tokens: dict[str, str],
    task_ids: set[UUID],
    task_name: str,
) -> tuple[UUID, UUID, int]:
    node_id = uuid4()
    created = client.post(
        "/api/v1/tasks",
        headers=_bearer(tokens[refs.creator]),
        json={
            "task_name": task_name,
            "main_assignee_employee_no": refs.assignee,
            "reviewer_employee_no": refs.reviewer,
            "department_id": str(refs.department_id),
            "acceptance_criteria": "Completion review integration accepted",
            "nodes": [
                {
                    "node_id": str(node_id),
                    "node_order": 1,
                    "node_name": f"{task_name} deliverable",
                    "owner_employee_no": refs.assignee,
                }
            ],
        },
    )
    assert created.status_code == 201
    task_id = UUID(created.json()["task_id"])
    task_ids.add(task_id)

    submitted = _post_action(
        client,
        tokens[refs.creator],
        task_id,
        "submit-for-confirmation",
        1,
    )
    sent = _post_action(
        client,
        tokens[refs.creator],
        task_id,
        "confirm-and-send",
        2,
    )
    accepted = _post_action(
        client,
        tokens[refs.assignee],
        task_id,
        "accept",
        3,
    )
    started = client.post(
        f"/api/v1/tasks/{task_id}/nodes/{node_id}/actions/start",
        headers=_bearer(tokens[refs.assignee]),
        json={"expected_task_version": 4},
    )
    progressed = client.patch(
        f"/api/v1/tasks/{task_id}/nodes/{node_id}/progress",
        headers=_bearer(tokens[refs.assignee]),
        json={
            "expected_task_version": 5,
            "progress_percent": 75,
            "actual_hours": "2.5",
        },
    )
    completed = client.post(
        f"/api/v1/tasks/{task_id}/nodes/{node_id}/actions/complete",
        headers=_bearer(tokens[refs.assignee]),
        json={"expected_task_version": 6},
    )
    assert [
        response.status_code
        for response in (
            submitted,
            sent,
            accepted,
            started,
            progressed,
            completed,
        )
    ] == [200] * 6
    assert completed.json()["task_version"] == 7
    return task_id, node_id, 7


def _cleanup(
    engine: Engine,
    refs: CompletionReferences,
    task_ids: set[UUID],
) -> None:
    with engine.begin() as connection:
        connection.execute(
            delete(OperationLog).where(OperationLog.operator_employee_no.in_(refs.employee_nos))
        )
        if task_ids:
            connection.execute(
                delete(TaskStatusLog).where(TaskStatusLog.task_id.in_(task_ids))
            )
            connection.execute(
                delete(TaskCompletionReview).where(
                    TaskCompletionReview.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskNodeDependency).where(
                    TaskNodeDependency.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskNodeParticipant).where(
                    TaskNodeParticipant.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskParticipant).where(
                    TaskParticipant.task_id.in_(task_ids)
                )
            )
            connection.execute(
                delete(TaskNode).where(TaskNode.task_id.in_(task_ids))
            )
            connection.execute(delete(Task).where(Task.task_id.in_(task_ids)))
        connection.execute(
            delete(User).where(User.employee_no.in_(refs.employee_nos))
        )
        connection.execute(
            delete(Department).where(
                Department.department_id == refs.department_id
            )
        )

    if task_ids:
        with engine.connect() as connection:
            residual = sum(
                connection.execute(statement).scalar_one()
                for statement in (
                    select(func.count()).select_from(TaskStatusLog).where(
                        TaskStatusLog.task_id.in_(task_ids)
                    ),
                    select(func.count()).select_from(TaskCompletionReview).where(
                        TaskCompletionReview.task_id.in_(task_ids)
                    ),
                    select(func.count()).select_from(TaskNode).where(
                        TaskNode.task_id.in_(task_ids)
                    ),
                    select(func.count()).select_from(Task).where(
                        Task.task_id.in_(task_ids)
                    ),
                )
            )
        assert residual == 0


def test_completion_review_rounds_rework_api_and_atomicity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        pytest.fail("Wave 1 target is not the approved isolated database")

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c statement_timeout=5000 -c lock_timeout=1000"},
    )
    refs = _references()
    task_ids: set[UUID] = set()
    try:
        assert set(inspect(engine).get_table_names(schema="public")) - {
            "alembic_version"
        } == EXPECTED_TABLES
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalars().all() == [EXPECTED_REVISION]

        factory = sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )
        with factory.begin() as session:
            session.add(
                Department(
                    department_id=refs.department_id,
                    department_name="Wave 1 Completion Integration",
                    department_type="team",
                    department_path=f"/{refs.department_id}",
                    status="active",
                )
            )
            session.add_all(
                [
                    User(
                        employee_no=employee_no,
                        name=employee_no,
                        department_id=refs.department_id,
                        role_type="employee",
                        status="active",
                    )
                    for employee_no in refs.employee_nos
                ]
            )

        settings = Settings(
            app_env="test",
            database_url=database_url,
            auth_mode="prototype",
            prototype_auth_enabled=True,
            prototype_user_employee_nos=",".join(refs.employee_nos),
            jwt_secret_key=secrets.token_urlsafe(48),
            jwt_issuer="smart-task-board-wave1-integration",
            jwt_audience="smart-task-board-wave1-client",
            allow_test_employee_header=False,
        )

        def regular_uow_override():
            return lambda: UnitOfWork(factory)

        def override_get_db() -> Iterator[Session]:
            session = factory()
            try:
                yield session
            finally:
                session.close()

        monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
        app.dependency_overrides[dependencies.get_uow_factory] = (
            regular_uow_override
        )
        app.dependency_overrides[dependencies.get_db] = override_get_db
        app.dependency_overrides[get_settings] = lambda: settings

        with TestClient(app, raise_server_exceptions=False) as client:
            tokens = {
                employee_no: _login(client, employee_no)
                for employee_no in refs.employee_nos
            }
            overall_task_id, overall_node_id, overall_version = (
                _create_ready_task(
                    client,
                    refs,
                    tokens,
                    task_ids,
                    "Wave 1 Overall Rework",
                )
            )
            node_task_id, node_id, node_version = _create_ready_task(
                client,
                refs,
                tokens,
                task_ids,
                "Wave 1 Node Rework",
            )

            first_submission = _post_action(
                client,
                tokens[refs.assignee],
                overall_task_id,
                "submit-completion",
                overall_version,
                completion_note="Initial overall submission",
                deliverable_summary="Overall artifact version one",
            )
            assert first_submission.status_code == 200
            assert (
                first_submission.json()["status"],
                first_submission.json()["task_version"],
            ) == ("pending_review", 8)
            overall_review_one = first_submission.json()["review"]
            overall_review_one_id = UUID(
                overall_review_one["completion_review_id"]
            )
            assert (
                overall_review_one["review_round"],
                overall_review_one["review_status"],
                overall_review_one["submitted_task_version"],
            ) == (1, "submitted", 8)

            pending_actions = client.get(
                f"/api/v1/tasks/{overall_task_id}/available-actions",
                headers=_bearer(tokens[refs.reviewer]),
            )
            reviewer_inbox = client.get(
                "/api/v1/tasks/inbox?action_code=approve_completion",
                headers=_bearer(tokens[refs.reviewer]),
            )
            assert pending_actions.status_code == reviewer_inbox.status_code == 200
            assert pending_actions.json()["allowed_actions"] == [
                "approve_completion",
                "reject_completion",
            ]
            assert reviewer_inbox.json()["total"] == 1
            assert len(reviewer_inbox.json()["items"]) == 1
            acceptance_item = reviewer_inbox.json()["items"][0]
            assert acceptance_item["task"]["task_id"] == str(overall_task_id)
            assert acceptance_item["inbox_item_type"] == "approve_completion"
            assert acceptance_item["allowed_actions"] == [
                "approve_completion",
                "reject_completion",
            ]

            class FailingCompletionLogUnitOfWork(UnitOfWork):
                def __enter__(self):
                    entered = super().__enter__()
                    real_add = self.task_status_logs.add

                    def fail_rejection(log: TaskStatusLog) -> TaskStatusLog:
                        if log.action_type == "completion_rejected":
                            raise RuntimeError("forced completion log failure")
                        return real_add(log)

                    self.task_status_logs.add = fail_rejection
                    return entered

            def failing_uow_override():
                return lambda: FailingCompletionLogUnitOfWork(factory)

            app.dependency_overrides[dependencies.get_uow_factory] = (
                failing_uow_override
            )
            failed_rejection = _post_action(
                client,
                tokens[refs.reviewer],
                overall_task_id,
                "reject-completion",
                8,
                completion_review_id=str(overall_review_one_id),
                reject_reason="This attempt must roll back",
            )
            _assert_error(failed_rejection, 500, "internal_server_error")
            app.dependency_overrides[dependencies.get_uow_factory] = (
                regular_uow_override
            )
            with factory() as session:
                stored_task = session.get(Task, overall_task_id)
                stored_review = session.get(
                    TaskCompletionReview,
                    overall_review_one_id,
                )
                assert stored_task is not None and stored_review is not None
                assert (stored_task.status, stored_task.task_version) == (
                    "pending_review",
                    8,
                )
                assert stored_review.review_status == "submitted"
                assert session.scalar(
                    select(func.count())
                    .select_from(TaskStatusLog)
                    .where(
                        TaskStatusLog.task_id == overall_task_id,
                        TaskStatusLog.action_type == "completion_rejected",
                    )
                ) == 0

            stale_rejection = _post_action(
                client,
                tokens[refs.reviewer],
                overall_task_id,
                "reject-completion",
                7,
                completion_review_id=str(overall_review_one_id),
                reject_reason="Stale",
            )
            outsider_rejection = _post_action(
                client,
                tokens[refs.outsider],
                overall_task_id,
                "reject-completion",
                8,
                completion_review_id=str(overall_review_one_id),
                reject_reason="Not allowed",
            )
            _assert_error(stale_rejection, 409, "task_version_conflict")
            _assert_error(outsider_rejection, 403, "permission_denied")

            cross_node = _post_action(
                client,
                tokens[refs.reviewer],
                overall_task_id,
                "reject-completion",
                8,
                completion_review_id=str(overall_review_one_id),
                reject_reason="Wrong task node",
                rework_node_id=str(node_id),
            )
            _assert_error(cross_node, 422, "business_validation_error")

            node_submission = _post_action(
                client,
                tokens[refs.assignee],
                node_task_id,
                "submit-completion",
                node_version,
                completion_note="Initial node submission",
                deliverable_summary="Node artifact version one",
            )
            assert node_submission.status_code == 200
            node_review_one_id = UUID(
                node_submission.json()["review"]["completion_review_id"]
            )
            cross_review = _post_action(
                client,
                tokens[refs.reviewer],
                node_task_id,
                "reject-completion",
                8,
                completion_review_id=str(overall_review_one_id),
                reject_reason="Wrong task review",
            )
            _assert_error(cross_review, 404, "entity_not_found")
            cross_review_detail = client.get(
                f"/api/v1/tasks/{node_task_id}/completion-reviews/"
                f"{overall_review_one_id}",
                headers=_bearer(tokens[refs.reviewer]),
            )
            _assert_error(cross_review_detail, 404, "entity_not_found")

            overall_rejected = _post_action(
                client,
                tokens[refs.reviewer],
                overall_task_id,
                "reject-completion",
                8,
                completion_review_id=str(overall_review_one_id),
                reject_reason="Revise the overall evidence",
            )
            assert overall_rejected.status_code == 200
            assert (
                overall_rejected.json()["status"],
                overall_rejected.json()["task_version"],
                overall_rejected.json()["review"]["review_status"],
                overall_rejected.json()["review"]["reviewed_task_version"],
            ) == ("in_progress", 9, "rejected", 9)
            repeated_decision = _post_action(
                client,
                tokens[refs.reviewer],
                overall_task_id,
                "approve-completion",
                9,
                completion_review_id=str(overall_review_one_id),
            )
            _assert_error(repeated_decision, 409, "invalid_state_transition")

            first_history = client.get(
                f"/api/v1/tasks/{overall_task_id}/completion-reviews",
                headers=_bearer(tokens[refs.assignee]),
                params={"limit": 1, "offset": 0},
            )
            assert first_history.status_code == 200
            assert (
                first_history.json()["total"],
                first_history.json()["limit"],
                first_history.json()["offset"],
            ) == (1, 1, 0)
            assert first_history.json()["items"][0]["review_status"] == (
                "rejected"
            )

            overall_second_submission = _post_action(
                client,
                tokens[refs.assignee],
                overall_task_id,
                "submit-completion",
                9,
                completion_note="Revised overall submission",
                deliverable_summary="Overall artifact version two",
            )
            assert overall_second_submission.status_code == 200
            overall_review_two_id = UUID(
                overall_second_submission.json()["review"][
                    "completion_review_id"
                ]
            )
            assert (
                overall_second_submission.json()["task_version"],
                overall_second_submission.json()["review"]["review_round"],
            ) == (10, 2)
            outsider_approval = _post_action(
                client,
                tokens[refs.outsider],
                overall_task_id,
                "approve-completion",
                10,
                completion_review_id=str(overall_review_two_id),
            )
            _assert_error(outsider_approval, 403, "permission_denied")
            overall_approved = _post_action(
                client,
                tokens[refs.reviewer],
                overall_task_id,
                "approve-completion",
                10,
                completion_review_id=str(overall_review_two_id),
            )
            assert (
                overall_approved.status_code,
                overall_approved.json()["status"],
                overall_approved.json()["task_version"],
                overall_approved.json()["review"]["review_status"],
            ) == (200, "completed", 11, "approved")

            history_page_one = client.get(
                f"/api/v1/tasks/{overall_task_id}/completion-reviews",
                headers=_bearer(tokens[refs.reviewer]),
                params={"limit": 1, "offset": 0},
            )
            history_page_two = client.get(
                f"/api/v1/tasks/{overall_task_id}/completion-reviews",
                headers=_bearer(tokens[refs.reviewer]),
                params={"limit": 1, "offset": 1},
            )
            assert history_page_one.status_code == history_page_two.status_code == 200
            assert history_page_one.json()["total"] == 2
            assert history_page_one.json()["items"][0][
                "completion_review_id"
            ] == str(overall_review_two_id)
            assert history_page_two.json()["items"][0][
                "completion_review_id"
            ] == str(overall_review_one_id)
            overall_review_detail = client.get(
                f"/api/v1/tasks/{overall_task_id}/completion-reviews/"
                f"{overall_review_one_id}",
                headers=_bearer(tokens[refs.assignee]),
            )
            assert overall_review_detail.status_code == 200
            assert overall_review_detail.json()["reject_reason"] == (
                "Revise the overall evidence"
            )
            outsider_history = client.get(
                f"/api/v1/tasks/{overall_task_id}/completion-reviews",
                headers=_bearer(tokens[refs.outsider]),
            )
            _assert_error(outsider_history, 403, "permission_denied")

            with factory() as session:
                original_node = session.get(TaskNode, node_id)
                assert original_node is not None
                original_completed_at = original_node.completed_at
                assert original_completed_at is not None
                assert original_node.actual_hours == Decimal("2.5")

            node_rejected = _post_action(
                client,
                tokens[refs.reviewer],
                node_task_id,
                "reject-completion",
                8,
                completion_review_id=str(node_review_one_id),
                reject_reason="Rework the selected node",
                rework_node_id=str(node_id),
            )
            assert (
                node_rejected.status_code,
                node_rejected.json()["status"],
                node_rejected.json()["task_version"],
                node_rejected.json()["review"]["rework_node_id"],
            ) == (200, "in_progress", 9, str(node_id))
            with factory() as session:
                unchanged_node = session.get(TaskNode, node_id)
                assert unchanged_node is not None
                assert (
                    unchanged_node.status,
                    unchanged_node.progress_percent,
                    unchanged_node.completed_at,
                    unchanged_node.actual_hours,
                ) == ("completed", 100, original_completed_at, Decimal("2.5"))

            rework_actions = client.get(
                f"/api/v1/tasks/{node_task_id}/available-actions",
                headers=_bearer(tokens[refs.reviewer]),
            )
            rework_inbox = client.get(
                "/api/v1/tasks/inbox?action_code=reopen_node",
                headers=_bearer(tokens[refs.reviewer]),
            )
            assert rework_actions.status_code == rework_inbox.status_code == 200
            assert rework_actions.json()["allowed_actions"] == []
            assert rework_actions.json()["nodes"] == [
                {"node_id": str(node_id), "allowed_actions": ["reopen_node"]}
            ]
            assert rework_inbox.json()["total"] == 1
            assert len(rework_inbox.json()["items"]) == 1
            assert rework_inbox.json()["items"][0]["allowed_actions"] == [
                "reopen_node"
            ]

            unauthorized_reopen = client.post(
                f"/api/v1/tasks/{node_task_id}/nodes/{node_id}/actions/reopen",
                headers=_bearer(tokens[refs.assignee]),
                json={
                    "expected_task_version": 9,
                    "completion_review_id": str(node_review_one_id),
                },
            )
            _assert_error(unauthorized_reopen, 403, "permission_denied")
            reopened = client.post(
                f"/api/v1/tasks/{node_task_id}/nodes/{node_id}/actions/reopen",
                headers=_bearer(tokens[refs.reviewer]),
                json={
                    "expected_task_version": 9,
                    "completion_review_id": str(node_review_one_id),
                },
            )
            assert (
                reopened.status_code,
                reopened.json()["node_status"],
                reopened.json()["progress_percent"],
                reopened.json()["task_version"],
            ) == (200, "in_progress", 0, 10)
            with factory() as session:
                reopened_node = session.get(TaskNode, node_id)
                assert reopened_node is not None
                assert (
                    reopened_node.status,
                    reopened_node.progress_percent,
                    reopened_node.completed_at,
                    reopened_node.actual_hours,
                ) == ("in_progress", 0, None, Decimal("2.5"))

            duplicate_reopen = client.post(
                f"/api/v1/tasks/{node_task_id}/nodes/{node_id}/actions/reopen",
                headers=_bearer(tokens[refs.reviewer]),
                json={
                    "expected_task_version": 10,
                    "completion_review_id": str(node_review_one_id),
                },
            )
            _assert_error(duplicate_reopen, 409, "invalid_state_transition")
            premature_submission = _post_action(
                client,
                tokens[refs.assignee],
                node_task_id,
                "submit-completion",
                10,
                completion_note="Premature",
                deliverable_summary="Node is still open",
            )
            _assert_error(
                premature_submission,
                422,
                "business_validation_error",
            )

            second_progress = client.patch(
                f"/api/v1/tasks/{node_task_id}/nodes/{node_id}/progress",
                headers=_bearer(tokens[refs.assignee]),
                json={
                    "expected_task_version": 10,
                    "progress_percent": 80,
                    "actual_hours": "3.0",
                },
            )
            second_completion = client.post(
                f"/api/v1/tasks/{node_task_id}/nodes/{node_id}/actions/complete",
                headers=_bearer(tokens[refs.assignee]),
                json={"expected_task_version": 11},
            )
            assert (
                second_progress.status_code,
                second_progress.json()["task_version"],
                second_completion.status_code,
                second_completion.json()["task_version"],
            ) == (200, 11, 200, 12)

            node_second_submission = _post_action(
                client,
                tokens[refs.assignee],
                node_task_id,
                "submit-completion",
                12,
                completion_note="Reworked node completed",
                deliverable_summary="Node artifact version two",
            )
            assert node_second_submission.status_code == 200
            node_review_two_id = UUID(
                node_second_submission.json()["review"]["completion_review_id"]
            )
            assert (
                node_second_submission.json()["task_version"],
                node_second_submission.json()["review"]["review_round"],
            ) == (13, 2)
            node_approved = _post_action(
                client,
                tokens[refs.reviewer],
                node_task_id,
                "approve-completion",
                13,
                completion_review_id=str(node_review_two_id),
            )
            assert (
                node_approved.status_code,
                node_approved.json()["status"],
                node_approved.json()["task_version"],
            ) == (200, "completed", 14)

            node_logs_response = client.get(
                f"/api/v1/tasks/{node_task_id}/status-logs",
                headers=_bearer(tokens[refs.reviewer]),
                params={"limit": 100},
            )
            node_history = client.get(
                f"/api/v1/tasks/{node_task_id}/completion-reviews",
                headers=_bearer(tokens[refs.reviewer]),
            )
            final_actions = client.get(
                f"/api/v1/tasks/{node_task_id}/available-actions",
                headers=_bearer(tokens[refs.reviewer]),
            )
            assert (
                node_logs_response.status_code,
                node_history.status_code,
                final_actions.status_code,
            ) == (200, 200, 200)
            node_logs = node_logs_response.json()["items"]
            assert sum(
                log["action_type"] == "node_completed" for log in node_logs
            ) == 2
            reopen_logs = [
                log for log in node_logs if log["action_type"] == "node_reopened"
            ]
            assert len(reopen_logs) == 1
            assert (
                reopen_logs[0]["business_ref_type"],
                reopen_logs[0]["business_ref_id"],
            ) == ("completion_review", str(node_review_one_id))
            assert node_history.json()["total"] == 2
            assert [
                item["review_round"] for item in node_history.json()["items"]
            ] == [2, 1]
            assert final_actions.json()["allowed_actions"] == []
            assert all(
                not item["allowed_actions"]
                for item in final_actions.json()["nodes"]
            )
    finally:
        app.dependency_overrides.clear()
        try:
            _cleanup(engine, refs, task_ids)
        finally:
            engine.dispose()
