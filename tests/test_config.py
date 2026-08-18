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
