from uuid import uuid4

import pytest

from app.services.dependency_graph import validate_dependency_graph
from app.services.errors import BusinessValidationError, DependencyCycleError


def test_valid_dependency_graph_is_accepted() -> None:
    first, second, third = uuid4(), uuid4(), uuid4()

    validate_dependency_graph(
        [first, second, third],
        [(first, second), (second, third)],
    )


@pytest.mark.parametrize("kind", ["missing", "self", "duplicate"])
def test_invalid_dependency_edges_are_rejected(kind: str) -> None:
    first, second, missing = uuid4(), uuid4(), uuid4()
    edges = {
        "missing": [(first, missing)],
        "self": [(first, first)],
        "duplicate": [(first, second), (first, second)],
    }[kind]

    with pytest.raises(BusinessValidationError):
        validate_dependency_graph([first, second], edges)


def test_dependency_cycle_is_rejected() -> None:
    first, second, third = uuid4(), uuid4(), uuid4()

    with pytest.raises(DependencyCycleError):
        validate_dependency_graph(
            [first, second, third],
            [(first, second), (second, third), (third, first)],
        )
