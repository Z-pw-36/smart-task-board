from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import AuthenticationRequiredError
from app.db.session import SessionLocal, get_db
from app.db.unit_of_work import UnitOfWork
from app.services.task_node_workflow import TaskNodeWorkflowService
from app.services.task_query import TaskQueryService
from app.services.task_workflow import TaskWorkflowService

UowFactory = Callable[[], UnitOfWork]


def get_current_employee_no(
    x_employee_no: Annotated[
        str | None,
        Header(
            alias="X-Employee-No",
            description=(
                "Prototype internal identity only; this is not secure authentication."
            ),
        ),
    ] = None,
) -> str:
    if x_employee_no is None or not x_employee_no.strip():
        raise AuthenticationRequiredError
    return x_employee_no.strip()


def get_uow_factory() -> UowFactory:
    return lambda: UnitOfWork(SessionLocal)


def get_task_workflow_service(
    uow_factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TaskWorkflowService:
    return TaskWorkflowService(uow_factory)


def get_task_node_workflow_service(
    uow_factory: Annotated[UowFactory, Depends(get_uow_factory)],
) -> TaskNodeWorkflowService:
    return TaskNodeWorkflowService(uow_factory)


def get_task_query_service(
    session: Annotated[Session, Depends(get_db)],
) -> TaskQueryService:
    return TaskQueryService(session)
