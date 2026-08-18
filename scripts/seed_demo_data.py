"""Opt-in, idempotent seed data for an isolated demo database only."""

import argparse
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Department, User
from app.repositories import DepartmentRepository, UserRepository

DEMO_DEPARTMENT_ID = UUID("c177061e-6ee2-4cae-9fd9-d403e343591e")
DEMO_DEPARTMENT_NAME = "SmartTaskBoard Demo Department"
DEMO_USERS = (
    ("E-CREATOR", "Demo Creator"),
    ("E-ASSIGNEE", "Demo Assignee"),
    ("E-REVIEWER", "Demo Reviewer"),
    ("E-OBSERVER", "Demo Observer"),
)


def validate_seed_target(database_url: str, confirmed_database_name: str) -> str:
    database_name = make_url(database_url).database
    if not database_name:
        raise ValueError("database name is unavailable")
    if database_name != confirmed_database_name:
        raise ValueError("confirmed database name does not match the configured target")
    if not database_name.endswith(("_test", "_demo")):
        raise ValueError("demo seed requires a database name ending in _test or _demo")
    return database_name


def seed_demo_data(session: Session, *, apply: bool) -> list[str]:
    departments = DepartmentRepository(session)
    users = UserRepository(session)
    actions: list[str] = []
    department = departments.get_by_id(DEMO_DEPARTMENT_ID)
    if department is None:
        actions.append("create demo department")
        if apply:
            department = Department(
                department_id=DEMO_DEPARTMENT_ID,
                department_name=DEMO_DEPARTMENT_NAME,
                department_type="department",
                department_path="/demo",
                status="active",
            )
            session.add(department)
            session.flush()
    elif department.department_name != DEMO_DEPARTMENT_NAME:
        raise ValueError("demo department ID already belongs to non-demo data")
    for employee_no, name in DEMO_USERS:
        existing = users.get_by_employee_no(employee_no)
        if existing is not None:
            actions.append(f"skip existing demo employee {employee_no}")
            continue
        actions.append(f"create demo employee {employee_no}")
        if apply:
            session.add(
                User(
                    employee_no=employee_no,
                    name=name,
                    department_id=DEMO_DEPARTMENT_ID,
                    role_type="employee",
                    status="active",
                )
            )
    if apply:
        session.commit()
    else:
        session.rollback()
    return actions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="inspect actions and rollback")
    mode.add_argument("--apply", action="store_true", help="persist demo records")
    parser.add_argument(
        "--confirm-database-name",
        required=True,
        help="must exactly match the configured isolated _test or _demo database name",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    settings = get_settings()
    database_name = validate_seed_target(
        settings.database_url, arguments.confirm_database_name
    )
    print(f"Validated isolated demo target: {database_name}")
    with SessionLocal() as session:
        actions = seed_demo_data(session, apply=arguments.apply)
    for action in actions:
        print(action)
    print("Demo seed applied." if arguments.apply else "Dry run complete; no data persisted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
