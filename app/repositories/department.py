from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Department


class DepartmentRepository:
    """Read access for organizational departments."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, department_id: UUID) -> Department | None:
        statement = select(Department).where(
            Department.department_id == department_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_name(self, name: str) -> Department | None:
        statement = (
            select(Department)
            .where(Department.department_name == name)
            .order_by(Department.department_path, Department.department_id)
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()
