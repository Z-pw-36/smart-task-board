from collections import deque
from collections.abc import Iterable
from uuid import UUID

from app.services.errors import (
    BusinessValidationError,
    DependencyCycleError,
)


def validate_dependency_graph(
    node_ids: Iterable[UUID],
    dependency_edges: Iterable[tuple[UUID, UUID]],
) -> None:
    """Validate references, uniqueness, self edges, and directed acyclicity."""

    nodes = set(node_ids)
    edges = list(dependency_edges)
    seen_edges: set[tuple[UUID, UUID]] = set()
    adjacency: dict[UUID, set[UUID]] = {node_id: set() for node_id in nodes}
    indegree: dict[UUID, int] = dict.fromkeys(nodes, 0)

    for predecessor_id, successor_id in edges:
        if predecessor_id not in nodes or successor_id not in nodes:
            raise BusinessValidationError(
                "dependency nodes must belong to the same task"
            )
        if predecessor_id == successor_id:
            raise BusinessValidationError("a task node cannot depend on itself")
        edge = (predecessor_id, successor_id)
        if edge in seen_edges:
            raise BusinessValidationError("duplicate task node dependency")
        seen_edges.add(edge)
        adjacency[predecessor_id].add(successor_id)
        indegree[successor_id] += 1

    ready = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        node_id = ready.popleft()
        visited += 1
        for successor_id in adjacency[node_id]:
            indegree[successor_id] -= 1
            if indegree[successor_id] == 0:
                ready.append(successor_id)

    if visited != len(nodes):
        raise DependencyCycleError("task node dependency graph contains a cycle")
