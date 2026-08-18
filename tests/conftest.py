import os
from collections.abc import Iterator

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@127.0.0.1:5432/smart_task_board_test",
)

from app.core.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    """Keep settings tests isolated from one another."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
