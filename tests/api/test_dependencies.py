import pytest

from app.api.dependencies import get_current_employee_no
from app.api.errors import AuthenticationRequiredError


def test_employee_header_is_trimmed() -> None:
    assert get_current_employee_no("  E001  ") == "E001"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_employee_header_is_required(value: str | None) -> None:
    with pytest.raises(AuthenticationRequiredError):
        get_current_employee_no(value)
