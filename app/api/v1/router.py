from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.business import router as business_router
from app.api.v1.me import router as me_router
from app.api.v1.progress_issues import router as progress_issues_router
from app.api.v1.task_board import router as task_board_router
from app.api.v1.tasks import router as tasks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(me_router)
api_router.include_router(business_router)
api_router.include_router(task_board_router)
api_router.include_router(progress_issues_router)
api_router.include_router(tasks_router)
