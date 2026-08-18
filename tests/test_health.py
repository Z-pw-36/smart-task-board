from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health_live_does_not_access_database(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called() -> None:
        raise AssertionError("live health check must not access the database")

    monkeypatch.setattr("app.main.check_database", fail_if_called)
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_health_ready_when_database_is_available(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.main.check_database", lambda: None)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert response.headers["X-Request-ID"]


def test_health_ready_when_database_is_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive_detail = (
        "database_url=postgresql+psycopg://admin:secret@127.0.0.1/private "
        "password=secret"
    )

    def unavailable() -> None:
        raise RuntimeError(sensitive_detail)

    monkeypatch.setattr("app.main.check_database", unavailable)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert response.headers["X-Request-ID"]
    assert sensitive_detail not in response.text
    assert "admin:secret" not in response.text
    assert "password=secret" not in response.text


def test_valid_client_request_id_is_returned(client: TestClient) -> None:
    request_id = "client.request-123_OK"

    response = client.get("/health/live", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


@pytest.mark.parametrize("request_id", ["invalid/request-id", "a" * 129])
def test_invalid_client_request_id_is_replaced(
    client: TestClient,
    request_id: str,
) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": request_id})

    returned_request_id = response.headers["X-Request-ID"]
    assert response.status_code == 200
    assert returned_request_id != request_id
    UUID(returned_request_id)
