from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scripts.seed_demo_data import (
    DEMO_DEPARTMENT_ID,
    build_parser,
    seed_demo_data,
    validate_seed_target,
)


def test_seed_requires_explicit_mode_and_database_confirmation() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(["--dry-run"])


def test_seed_accepts_only_exact_isolated_test_or_demo_database_name() -> None:
    url = "postgresql+psycopg://user:hidden@localhost/smarttaskboard_demo"
    assert validate_seed_target(url, "smarttaskboard_demo") == "smarttaskboard_demo"
    with pytest.raises(ValueError, match="does not match"):
        validate_seed_target(url, "another_demo")
    with pytest.raises(ValueError, match="ending in"):
        validate_seed_target(
            "postgresql+psycopg://user:hidden@localhost/company", "company"
        )


def test_dry_run_never_flushes_or_commits() -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None
    actions = seed_demo_data(session, apply=False)
    assert "create demo department" in actions
    session.add.assert_not_called()
    session.flush.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_apply_skips_existing_users_without_overwriting() -> None:
    session = MagicMock()
    department = SimpleNamespace(
        department_id=DEMO_DEPARTMENT_ID,
        department_name="SmartTaskBoard Demo Department",
    )
    existing_user = SimpleNamespace(employee_no="E-CREATOR")
    results = [department, existing_user, None, None, None]
    session.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda value=value: value)
        for value in results
    ]
    actions = seed_demo_data(session, apply=True)
    assert "skip existing demo employee E-CREATOR" in actions
    session.commit.assert_called_once()
    added_employee_nos = {
        call.args[0].employee_no
        for call in session.add.call_args_list
        if hasattr(call.args[0], "employee_no")
    }
    assert "E-CREATOR" not in added_employee_nos
