from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Task, TaskNode, TaskNodeDependency, TaskNodeParticipant, TaskParticipant
from app.repositories import TaskNodeRepository, TaskRepository, UserRepository
from app.services.errors import EntityNotFoundError, PermissionDeniedError

DUE_WINDOW_DAYS = 7


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _task_actions(
    task: Task,
    actor: str,
    nodes: list[TaskNode],
) -> list[str]:
    if task.status == "draft" and actor == task.creator_employee_no:
        if task.main_assignee_employee_no is not None and nodes:
            return ["submit_for_confirmation"]
        return []
    if task.status == "pending_confirmation" and actor == task.creator_employee_no:
        if task.main_assignee_employee_no == actor:
            return ["confirm_self_assigned"]
        return ["confirm_and_send"]
    if task.status == "pending_acceptance" and actor == task.main_assignee_employee_no:
        return ["accept", "return"]
    if task.status == "returned" and actor == task.creator_employee_no:
        return ["resend"]
    if task.status == "in_progress" and actor == task.main_assignee_employee_no:
        if nodes and all(node.status == "completed" for node in nodes):
            return ["submit_completion"]
    reviewer = task.reviewer_employee_no or task.creator_employee_no
    if task.status == "pending_review" and actor == reviewer:
        return ["approve_completion"]
    return []


def _node_actions(
    task: Task,
    node: TaskNode,
    actor: str,
    dependencies: list[TaskNodeDependency],
    nodes_by_id: dict[UUID, TaskNode],
) -> list[str]:
    if task.status != "in_progress":
        return []
    expected_actor = node.owner_employee_no or task.main_assignee_employee_no
    if expected_actor is None or actor != expected_actor:
        return []
    if node.status == "pending":
        predecessors = [
            nodes_by_id.get(item.predecessor_node_id)
            for item in dependencies
            if item.successor_node_id == node.node_id
        ]
        if all(item is not None and item.status == "completed" for item in predecessors):
            return ["start_node"]
        return []
    if node.status == "in_progress":
        return ["update_node_progress", "complete_node"]
    return []


class TaskBoardQueryService:
    def __init__(self, session: Session, clock=lambda: datetime.now(UTC)) -> None:
        self._tasks = TaskRepository(session)
        self._nodes = TaskNodeRepository(session)
        self._users = UserRepository(session)
        self._clock = clock

    @staticmethod
    def _date_boundaries(
        deadline_from: date | None,
        deadline_to: date | None,
    ) -> tuple[datetime | None, datetime | None]:
        start = datetime.combine(deadline_from, time.min, UTC) if deadline_from else None
        end = (
            datetime.combine(deadline_to + timedelta(days=1), time.min, UTC)
            if deadline_to
            else None
        )
        return start, end

    def list_tasks(
        self,
        actor: str,
        *,
        relation: str,
        task_status: str | None,
        search: str | None,
        deadline_from: date | None,
        deadline_to: date | None,
        limit: int,
        offset: int,
    ) -> dict[str, object]:
        start, end = self._date_boundaries(deadline_from, deadline_to)
        tasks, total = self._tasks.list_related(
            actor,
            relation=relation,
            task_status=task_status,
            search=search.strip() if search and search.strip() else None,
            deadline_from=start,
            deadline_to=end,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [self._summary(task, actor) for task in tasks],
            "limit": limit,
            "offset": offset,
            "total": total,
        }

    def list_inbox(
        self,
        actor: str,
        *,
        action_code: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, object]:
        items: list[dict[str, object]] = []
        for task in self._tasks.list_inbox_candidates(actor):
            nodes, dependencies, _, _ = self._context(task.task_id)
            task_summary = self._summary(task, actor, context=(nodes, dependencies))
            task_actions = _task_actions(task, actor, nodes)
            if task.status == "pending_confirmation" and task_actions:
                items.append(
                    self._inbox_item(
                        "confirm_task", task, task_summary, None, task_actions
                    )
                )
            elif task.status == "pending_acceptance" and task_actions:
                items.append(
                    self._inbox_item(
                        "accept_task", task, task_summary, None, task_actions
                    )
                )
            elif task.status == "returned" and task_actions:
                items.append(
                    self._inbox_item("handle_returned_task", task, task_summary, None, task_actions)
                )
            elif task.status == "pending_review" and task_actions:
                items.append(
                    self._inbox_item(
                        "approve_completion", task, task_summary, None, task_actions
                    )
                )
            elif task.status == "in_progress":
                if "submit_completion" in task_actions:
                    items.append(
                        self._inbox_item(
                            "submit_completion", task, task_summary, None, ["submit_completion"]
                        )
                    )
                nodes_by_id = {node.node_id: node for node in nodes}
                for node in nodes:
                    node_actions = _node_actions(task, node, actor, dependencies, nodes_by_id)
                    for action in node_actions:
                        code = "update_node" if action == "update_node_progress" else action
                        items.append(
                            self._inbox_item(code, task, task_summary, node, [action])
                        )
        if action_code is not None:
            items = [item for item in items if item["action_code"] == action_code]
        items.sort(
            key=lambda item: (
                -_aware_utc(item["relevant_at"]).timestamp(),
                str(item["task"]["task_id"]),
                str(item["node"]["node_id"]) if item["node"] else "",
                item["action_code"],
            )
        )
        total = len(items)
        return {
            "items": items[offset : offset + limit],
            "limit": limit,
            "offset": offset,
            "total": total,
        }

    def available_actions(self, task_id: UUID, actor: str) -> dict[str, object]:
        task = self._tasks.get_by_id(task_id)
        if task is None:
            raise EntityNotFoundError("task was not found")
        if not self._tasks.is_related(task_id, actor):
            raise PermissionDeniedError("actor cannot read this task")
        nodes, dependencies, _, _ = self._context(task_id)
        nodes_by_id = {node.node_id: node for node in nodes}
        return {
            "task_id": task.task_id,
            "task_version": task.task_version,
            "allowed_actions": _task_actions(task, actor, nodes),
            "nodes": [
                {
                    "node_id": node.node_id,
                    "allowed_actions": _node_actions(
                        task, node, actor, dependencies, nodes_by_id
                    ),
                }
                for node in nodes
            ],
        }

    def dashboard_summary(self, actor: str) -> dict[str, object]:
        now = _aware_utc(self._clock())
        due_end = now + timedelta(days=DUE_WINDOW_DAYS)
        recent = self._tasks.list_recent_related(actor, limit=5)
        inbox_total = self.list_inbox(actor, action_code=None, limit=1, offset=0)["total"]
        return {
            "created_task_count": self._tasks.count_related(actor, relation="created"),
            "assigned_task_count": self._tasks.count_related(actor, relation="assigned"),
            "inbox_count": inbox_total,
            "in_progress_count": self._tasks.count_related(
                actor, task_status="in_progress"
            ),
            "due_within_7_days_count": self._tasks.count_related(
                actor,
                deadline_from=now,
                deadline_to=due_end,
                exclude_completed=True,
            ),
            "overdue_count": self._tasks.count_related(
                actor,
                deadline_to=now,
                exclude_completed=True,
            ),
            "due_window_days": DUE_WINDOW_DAYS,
            "recent_tasks": [self._summary(task, actor) for task in recent],
        }

    def _context(
        self,
        task_id: UUID,
    ) -> tuple[
        list[TaskNode],
        list[TaskNodeDependency],
        list[TaskParticipant],
        list[TaskNodeParticipant],
    ]:
        return (
            self._nodes.list_nodes(task_id),
            self._nodes.list_dependencies(task_id),
            self._tasks.list_participants(task_id),
            self._nodes.list_participants_by_task_id(task_id),
        )

    def _summary(
        self,
        task: Task,
        actor: str,
        *,
        context: tuple[list[TaskNode], list[TaskNodeDependency]] | None = None,
    ) -> dict[str, object]:
        if context is None:
            nodes, dependencies, participants, node_participants = self._context(task.task_id)
        else:
            nodes, dependencies = context
            participants = self._tasks.list_participants(task.task_id)
            node_participants = self._nodes.list_participants_by_task_id(task.task_id)
        employee_nos = tuple(
            item
            for item in {task.creator_employee_no, task.main_assignee_employee_no}
            if item is not None
        )
        people = {
            item.employee_no: item
            for item in self._users.list_by_employee_nos(employee_nos)
        }
        creator = people.get(task.creator_employee_no)
        assignee = (
            people.get(task.main_assignee_employee_no)
            if task.main_assignee_employee_no
            else None
        )
        now = _aware_utc(self._clock())
        deadline = _aware_utc(task.deadline) if task.deadline else None
        is_overdue = deadline is not None and task.status != "completed" and deadline < now
        relations: list[str] = []
        if actor == task.creator_employee_no:
            relations.append("created")
        if actor == task.main_assignee_employee_no:
            relations.append("assigned")
        if actor == task.report_to_employee_no:
            relations.append("report_to")
        if actor == task.reviewer_employee_no:
            relations.append("reviewer")
        if any(item.employee_no == actor for item in participants):
            relations.append("participant")
        if any(item.owner_employee_no == actor for item in nodes):
            relations.append("node_owner")
        if any(item.employee_no == actor for item in node_participants):
            relations.append("node_participant")
        return {
            "task_id": task.task_id,
            "task_no": task.task_no,
            "task_name": task.task_name,
            "status": task.status,
            "deadline": task.deadline,
            "is_urgent": task.is_urgent,
            "task_weight": task.task_weight,
            "task_version": task.task_version,
            "creator": {
                "employee_no": task.creator_employee_no,
                "name": creator.name if creator else task.creator_employee_no,
            },
            "main_assignee": (
                {
                    "employee_no": task.main_assignee_employee_no,
                    "name": assignee.name if assignee else task.main_assignee_employee_no,
                }
                if task.main_assignee_employee_no
                else None
            ),
            "current_user_relations": list(dict.fromkeys(relations)),
            "allowed_actions": _task_actions(task, actor, nodes),
            "is_overdue": is_overdue,
            "days_until_deadline": (
                (deadline.date() - now.date()).days if deadline is not None else None
            ),
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    def _inbox_item(
        self,
        action_code: str,
        task: Task,
        task_summary: dict[str, object],
        node: TaskNode | None,
        allowed_actions: list[str],
    ) -> dict[str, object]:
        endpoint = f"/api/v1/tasks/{task.task_id}"
        if node is not None:
            endpoint += f"/nodes/{node.node_id}"
        action_suffix = {
            "confirm_task": allowed_actions[0].replace("_", "-"),
            "accept_task": "accept",
            "handle_returned_task": "resend",
            "start_node": "start",
            "update_node": "progress",
            "complete_node": "complete",
            "submit_completion": "submit-completion",
            "approve_completion": "approve-completion",
        }[action_code]
        if action_code == "update_node":
            endpoint += "/progress"
        else:
            endpoint += f"/actions/{action_suffix}"
        reason = {
            "confirm_task": "Task is waiting for creator confirmation.",
            "accept_task": "Task is waiting for the main assignee.",
            "handle_returned_task": "Returned task is waiting to be resent.",
            "start_node": "Task node is ready to start.",
            "update_node": "Task node is in progress.",
            "complete_node": "Task node can be completed.",
            "submit_completion": "All task nodes are completed.",
            "approve_completion": "Task is waiting for completion review.",
        }[action_code]
        return {
            "inbox_item_type": action_code,
            "action_code": action_code,
            "task": task_summary,
            "node": (
                {
                    "node_id": node.node_id,
                    "node_name": node.node_name,
                    "status": node.status,
                    "progress_percent": node.progress_percent,
                    "owner_employee_no": node.owner_employee_no,
                }
                if node is not None
                else None
            ),
            "reason": reason,
            "expected_task_version": task.task_version,
            "endpoint": endpoint,
            "allowed_actions": allowed_actions,
            "is_overdue": task_summary["is_overdue"],
            "relevant_at": task.updated_at,
        }
