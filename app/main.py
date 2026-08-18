from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.api.errors import register_exception_handlers
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.db.session import check_database


def create_app(settings=None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    application = FastAPI(
        title=resolved_settings.app_name,
        debug=resolved_settings.app_debug,
        version="0.1.0",
    )
    application.add_middleware(RequestContextMiddleware)
    if resolved_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )
    register_exception_handlers(application)
    application.include_router(api_router)

    @application.get("/health/live", tags=["health"])
    def health_live() -> dict[str, str]:
        """Report whether the API process is running."""
        return {"status": "ok"}

    @application.get("/health/ready", tags=["health"])
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

    return application


app = create_app()
