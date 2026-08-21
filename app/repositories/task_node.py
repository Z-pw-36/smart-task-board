from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TaskNode, TaskNodeDependency, TaskNodeParticipant


class TaskNodeRepository:
    """Persistence operations for nodes, dependencies, and node participants."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_node(self, node: TaskNode) -> TaskNode:
        self.session.add(node)
        self.session.flush()
        return node

    def delete_node(self, node: TaskNode) -> None:
        self.session.delete(node)

    def get_node(self, node_id: UUID) -> TaskNode | None:
        statement = select(TaskNode).where(TaskNode.node_id == node_id)
        return self.session.execute(statement).scalar_one_or_none()

    def get_node_for_update(self, node_id: UUID) -> TaskNode | None:
        statement = (
            select(TaskNode)
            .where(TaskNode.node_id == node_id)
            .with_for_update()
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_nodes(self, task_id: UUID) -> list[TaskNode]:
        statement = (
            select(TaskNode)
            .where(TaskNode.task_id == task_id)
            .order_by(TaskNode.node_order, TaskNode.sort_weight, TaskNode.node_id)
        )
        return list(self.session.execute(statement).scalars().all())

    def add_dependency(
        self,
        dependency: TaskNodeDependency,
    ) -> TaskNodeDependency:
        self.session.add(dependency)
        self.session.flush()
        return dependency

    def delete_dependency(self, dependency: TaskNodeDependency) -> None:
        self.session.delete(dependency)

    def get_dependency(self, dependency_id: UUID) -> TaskNodeDependency | None:
        statement = select(TaskNodeDependency).where(
            TaskNodeDependency.dependency_id == dependency_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_dependencies(self, task_id: UUID) -> list[TaskNodeDependency]:
        statement = (
            select(TaskNodeDependency)
            .where(TaskNodeDependency.task_id == task_id)
            .order_by(
                TaskNodeDependency.predecessor_node_id,
                TaskNodeDependency.successor_node_id,
                TaskNodeDependency.dependency_type,
                TaskNodeDependency.dependency_id,
            )
        )
        return list(self.session.execute(statement).scalars().all())

    def list_predecessors(
        self,
        task_id: UUID,
        successor_node_id: UUID,
    ) -> list[TaskNodeDependency]:
        statement = (
            select(TaskNodeDependency)
            .where(
                TaskNodeDependency.task_id == task_id,
                TaskNodeDependency.successor_node_id == successor_node_id,
            )
            .order_by(
                TaskNodeDependency.predecessor_node_id,
                TaskNodeDependency.dependency_type,
                TaskNodeDependency.dependency_id,
            )
        )
        return list(self.session.execute(statement).scalars().all())

    def list_successors(
        self,
        task_id: UUID,
        predecessor_node_id: UUID,
    ) -> list[TaskNodeDependency]:
        statement = (
            select(TaskNodeDependency)
            .where(
                TaskNodeDependency.task_id == task_id,
                TaskNodeDependency.predecessor_node_id == predecessor_node_id,
            )
            .order_by(
                TaskNodeDependency.successor_node_id,
                TaskNodeDependency.dependency_type,
                TaskNodeDependency.dependency_id,
            )
        )
        return list(self.session.execute(statement).scalars().all())

    def add_participant(
        self,
        participant: TaskNodeParticipant,
    ) -> TaskNodeParticipant:
        self.session.add(participant)
        self.session.flush()
        return participant

    def delete_participant(self, participant: TaskNodeParticipant) -> None:
        self.session.delete(participant)

    def get_participant(
        self,
        node_participant_id: UUID,
    ) -> TaskNodeParticipant | None:
        statement = select(TaskNodeParticipant).where(
            TaskNodeParticipant.node_participant_id == node_participant_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_participants(
        self,
        task_id: UUID,
        node_id: UUID,
    ) -> list[TaskNodeParticipant]:
        statement = (
            select(TaskNodeParticipant)
            .where(
                TaskNodeParticipant.task_id == task_id,
                TaskNodeParticipant.node_id == node_id,
            )
            .order_by(
                TaskNodeParticipant.participant_role,
                TaskNodeParticipant.employee_no,
                TaskNodeParticipant.node_participant_id,
            )
        )
        return list(self.session.execute(statement).scalars().all())

    def list_participants_by_task_id(
        self,
        task_id: UUID,
    ) -> list[TaskNodeParticipant]:
        statement = (
            select(TaskNodeParticipant)
            .where(TaskNodeParticipant.task_id == task_id)
            .order_by(
                TaskNodeParticipant.node_id,
                TaskNodeParticipant.participant_role,
                TaskNodeParticipant.employee_no,
                TaskNodeParticipant.node_participant_id,
            )
        )
        return list(self.session.execute(statement).scalars().all())

    def find_participant(
        self,
        task_id: UUID,
        node_id: UUID,
        employee_no: str,
        participant_role: str,
    ) -> TaskNodeParticipant | None:
        statement = select(TaskNodeParticipant).where(
            TaskNodeParticipant.task_id == task_id,
            TaskNodeParticipant.node_id == node_id,
            TaskNodeParticipant.employee_no == employee_no,
            TaskNodeParticipant.participant_role == participant_role,
        )
        return self.session.execute(statement).scalar_one_or_none()
