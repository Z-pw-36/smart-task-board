from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    """Read access for employee identities."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_employee_no(self, employee_no: str) -> User | None:
        statement = select(User).where(User.employee_no == employee_no)
        return self.session.execute(statement).scalar_one_or_none()

    def get_by_employee_no_for_update(self, employee_no: str) -> User | None:
        statement = (
            select(User)
            .where(User.employee_no == employee_no)
            .with_for_update()
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_by_department(self, department_id: UUID) -> list[User]:
        statement = (
            select(User)
            .where(User.department_id == department_id)
            .order_by(User.name, User.employee_no)
        )
        return list(self.session.execute(statement).scalars().all())
