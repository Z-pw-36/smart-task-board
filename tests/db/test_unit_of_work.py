from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy.orm import Session

from app.db.unit_of_work import UnitOfWork


def _session_factory() -> tuple[Mock, MagicMock]:
    session = MagicMock(spec=Session)
    factory = Mock(return_value=session)
    return factory, session


def test_all_repositories_share_one_session_and_commit_is_explicit() -> None:
    factory, session = _session_factory()

    with UnitOfWork(factory) as uow:
        repositories = (
            uow.departments,
            uow.users,
            uow.task_inputs,
            uow.ai_extraction_records,
            uow.tasks,
            uow.task_nodes,
            uow.task_status_logs,
        )
        assert all(repository.session is session for repository in repositories)
        session.commit.assert_not_called()
        uow.commit()

    factory.assert_called_once_with()
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.close.assert_called_once_with()
    assert uow.session is None


def test_exit_without_commit_rolls_back_and_closes() -> None:
    factory, session = _session_factory()

    with UnitOfWork(factory):
        pass

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def test_exception_exit_rolls_back_closes_and_propagates() -> None:
    factory, session = _session_factory()

    with pytest.raises(RuntimeError, match="body failed"):
        with UnitOfWork(factory):
            raise RuntimeError("body failed")

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def test_explicit_rollback_is_not_repeated_on_exit() -> None:
    factory, session = _session_factory()

    with UnitOfWork(factory) as uow:
        uow.rollback()

    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def test_commit_failure_rolls_back_closes_and_propagates_original_error() -> None:
    factory, session = _session_factory()
    session.commit.side_effect = RuntimeError("commit failed")

    with pytest.raises(RuntimeError, match="commit failed"):
        with UnitOfWork(factory) as uow:
            uow.commit()

    session.commit.assert_called_once_with()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def test_transaction_methods_require_an_active_context() -> None:
    factory, _ = _session_factory()
    uow = UnitOfWork(factory)

    with pytest.raises(RuntimeError, match="not active"):
        uow.commit()
    with pytest.raises(RuntimeError, match="not active"):
        uow.rollback()
