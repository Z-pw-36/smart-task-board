from fastapi import FastAPI, HTTPException, status

from app.api import api_router
from app.api.errors import register_exception_handlers
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.db.session import check_database

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health/live", tags=["health"])
def health_live() -> dict[str, str]:
    """Report whether the API process is running."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def health_ready() -> dict[str, str]:
    """Report whether the API can reach its database."""
    try:
        check_database()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return {"status": "ready"}
