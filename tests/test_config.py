import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_default_timezone() -> None:
    settings = get_settings()

    assert settings.app_timezone == "Asia/Shanghai"


def test_app_name_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Smart Task Board Test API")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "Smart Task Board Test API"


def test_timezone_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_TIMEZONE", "UTC")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_timezone == "UTC"


def test_database_url_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "postgresql+psycopg://unit:unit@127.0.0.1:5432/unit_test"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == database_url
    assert settings.database_connect_timeout_seconds == 5


def test_database_connect_timeout_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://unit:unit@127.0.0.1:5432/unit_test",
    )
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "2")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_connect_timeout_seconds == 2


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_database_url_is_not_exposed_in_repr_or_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_url = "postgresql+psycopg://hidden:secret@127.0.0.1:5432/private"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    settings = get_settings()

    assert database_url not in repr(settings)
    captured = capsys.readouterr()
    assert database_url not in captured.out
    assert database_url not in captured.err


def test_ai_provider_defaults_to_fake() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        _env_file=None,
    )

    assert settings.ai_provider == "fake"


def test_openai_compatible_provider_requires_backend_environment() -> None:
    with pytest.raises(ValidationError, match="AI_API_KEY"):
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            ai_provider="openai_compatible",
            _env_file=None,
        )


def test_openai_compatible_settings_do_not_expose_secret_values() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        ai_provider="openai_compatible",
        ai_api_key="unit-secret-key",
        ai_base_url="https://unit.invalid/v1",
        ai_model="unit-model",
        _env_file=None,
    )

    rendered = repr(settings)
    assert "unit-secret-key" not in rendered
    assert "https://unit.invalid/v1" not in rendered
    assert "unit-model" not in rendered
