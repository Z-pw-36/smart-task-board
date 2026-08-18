from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError

from app.core.config import Settings

JWT_ALGORITHM = "HS256"


class InvalidPrototypeTokenError(Exception):
    """Raised when an isolated-demo JWT cannot be trusted."""


def create_access_token(
    employee_no: str,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> tuple[str, int]:
    """Create a short-lived prototype token; never use this as company SSO."""
    if settings.jwt_secret_key is None:
        raise RuntimeError("JWT secret is not configured")
    issued_at = now or datetime.now(UTC)
    expires_in = settings.jwt_expire_minutes * 60
    payload = {
        "sub": employee_no,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=expires_in),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )
    return token, expires_in


def decode_access_token(token: str, settings: Settings) -> str:
    if settings.jwt_secret_key is None:
        raise InvalidPrototypeTokenError
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except InvalidTokenError as exc:
        raise InvalidPrototypeTokenError from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise InvalidPrototypeTokenError
    return subject.strip()
