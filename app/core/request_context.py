import re
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _is_valid_request_id(value: str | None) -> bool:
    return bool(value and REQUEST_ID_PATTERN.fullmatch(value))


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request identifier to request context and response headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        client_request_id = request.headers.get("X-Request-ID")
        request_id = (
            client_request_id if _is_valid_request_id(client_request_id) else str(uuid4())
        )
        token = request_id_context.set(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_context.reset(token)
