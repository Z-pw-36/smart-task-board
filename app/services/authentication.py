from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token
from app.models import RefreshToken, User
from app.services.errors import PermissionDeniedError


def _now() -> datetime:
    return datetime.now(UTC)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AuthenticationService:
    """Issue short-lived access tokens and rotate opaque refresh tokens."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def issue(
        self, employee_no: str, *, client_id: str | None = None, user_agent: str | None = None
    ) -> dict[str, object]:
        user = self.session.get(User, employee_no)
        if user is None or user.status != "active":
            raise PermissionDeniedError("current identity is unavailable")
        access_token, expires_in = create_access_token(employee_no, self.settings)
        raw = secrets.token_urlsafe(48)
        now = _now()
        row = RefreshToken(
            employee_no=employee_no,
            token_hash=_digest(raw),
            family_id=uuid4(),
            issued_at=now,
            expires_at=now + timedelta(days=30),
            client_id=client_id,
            user_agent=user_agent,
        )
        self.session.add(row)
        self.session.commit()
        return {"access_token": access_token, "expires_in": expires_in, "refresh_token": raw}

    def rotate(
        self, raw_token: str, *, client_id: str | None = None, user_agent: str | None = None
    ) -> dict[str, object]:
        row = self.session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == _digest(raw_token))
            .with_for_update()
        )
        now = _now()
        if row is None or row.status != "active" or row.expires_at <= now:
            if row is not None and row.status == "active":
                row.status = "expired"
                self.session.commit()
            raise PermissionDeniedError("refresh token is invalid or expired")
        user = self.session.get(User, row.employee_no)
        if user is None or user.status != "active":
            row.status = "revoked"
            row.revoked_at = now
            self.session.commit()
            raise PermissionDeniedError("current identity is unavailable")
        access_token, expires_in = create_access_token(row.employee_no, self.settings)
        replacement_raw = secrets.token_urlsafe(48)
        replacement = RefreshToken(
            employee_no=row.employee_no,
            token_hash=_digest(replacement_raw),
            family_id=row.family_id,
            issued_at=now,
            expires_at=now + timedelta(days=30),
            client_id=client_id or row.client_id,
            user_agent=user_agent or row.user_agent,
        )
        self.session.add(replacement)
        self.session.flush()
        row.status = "rotated"
        row.rotated_at = now
        row.replaced_by_token_id = replacement.refresh_token_id
        self.session.commit()
        return {
            "access_token": access_token,
            "expires_in": expires_in,
            "refresh_token": replacement_raw,
        }

    def revoke(self, raw_token: str) -> None:
        row = self.session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_hash == _digest(raw_token))
            .with_for_update()
        )
        if row is not None and row.status == "active":
            row.status = "revoked"
            row.revoked_at = _now()
            self.session.commit()

    def revoke_employee(self, employee_no: str) -> int:
        rows = self.session.scalars(
            select(RefreshToken)
            .where(RefreshToken.employee_no == employee_no, RefreshToken.status == "active")
            .with_for_update()
        ).all()
        now = _now()
        for row in rows:
            row.status = "revoked"
            row.revoked_at = now
        self.session.commit()
        return len(rows)
