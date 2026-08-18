from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token
from app.models import User
from app.repositories import UserRepository
from app.services.errors import EntityNotFoundError, PermissionDeniedError

PROTOTYPE_WARNING = "Prototype authentication is for isolated demo use only."


class IdentityService:
    def __init__(self, session: Session) -> None:
        self._users = UserRepository(session)

    @staticmethod
    def _require_prototype_enabled(settings: Settings) -> None:
        if settings.auth_mode != "prototype" or not settings.prototype_auth_enabled:
            raise EntityNotFoundError("prototype authentication is unavailable")

    def list_prototype_users(self, settings: Settings) -> list[User]:
        self._require_prototype_enabled(settings)
        users = self._users.list_by_employee_nos(settings.prototype_employee_nos)
        by_employee_no = {user.employee_no: user for user in users if user.status == "active"}
        return [
            by_employee_no[employee_no]
            for employee_no in settings.prototype_employee_nos
            if employee_no in by_employee_no
        ]

    def prototype_login(self, employee_no: str, settings: Settings) -> tuple[User, str, int]:
        self._require_prototype_enabled(settings)
        if employee_no not in settings.prototype_employee_nos:
            raise PermissionDeniedError("prototype login failed")
        user = self._users.get_by_employee_no_with_department(employee_no)
        if user is None or user.status != "active":
            raise PermissionDeniedError("prototype login failed")
        token, expires_in = create_access_token(employee_no, settings)
        return user, token, expires_in

    def get_active_user(self, employee_no: str) -> User:
        user = self._users.get_by_employee_no_with_department(employee_no)
        if user is None or user.status != "active":
            raise PermissionDeniedError("current identity is unavailable")
        return user
