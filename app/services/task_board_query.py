from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from app.models import (
    Notification,
    Task,
    TaskChangeRequest,
    TaskCompletionReview,
    TaskConflict,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    TaskParticipant,
    TaskPriorityScore,
    WorkloadSnapshot,
)
from app.repositories import (
    ProgressReportRepository,
    TaskChangeRequestRepository,
    TaskCompletionReviewRepository,
    TaskIssueRepository,
    TaskNodeRepository,
    TaskRepository,
    TaskStatusLogRepository,
    UserRepository,
)
from app.services.business_capabilities import PermissionScopeService
from app.services.errors import EntityNotFoundError, PermissionDeniedError
from app.services.progress_report import task_report_period
from app.services.task_issue import issue_allowed_actions

DUE_WINDOW_DAYS = 7


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def completion_review_allowed_actions(
    task: Task,
    actor: str,
    current_review: TaskCompletionReview | None,
) -> list[str]:
    if (
        task.status == "pending_review"
        and current_review is not None
        and current_review.review_status == "submitted"
        and actor == current_review.reviewer_employee_no
    ):
        return ["approve_completion", "reject_completion"]
    return []


def _task_actions(
    task: Task,
    actor: str,
    nodes: list[TaskNode],
    *,
    has_non_closed_issue: bool = False,
    is_task_participant: bool = False,
    current_review: TaskCompletionReview | None = None,
    latest_review: TaskCompletionReview | None = None,
    rework_node_reopened: bool = True,
    pending_change_request: TaskChangeRequest | None = None,
    include_change_actions: bool = False,
) -> list[str]:
    actions: list[str] = []
    if task.status == "draft" and actor == task.creator_employee_no:
        if task.main_assignee_employee_no is not None and nodes:
            actions.append("submit_for_confirmation")
    elif task.status == "pending_confirmation" and actor == task.creator_employee_no:
        if task.main_assignee_employee_no == actor:
            actions.append("confirm_self_assigned")
        else:
            actions.append("confirm_and_send")
    elif task.status == "pending_acceptance" and actor == task.main_assignee_employee_no:
        actions.extend(["accept", "return"])
    elif task.status == "returned" and actor == task.creator_employee_no:
        actions.append("resend")
    elif task.status == "in_progress":
        is_main_assignee = actor == task.main_assignee_employee_no
        can_report_issue = (
            actor in {task.creator_employee_no, task.main_assignee_employee_no}
            or is_task_participant
        )
        actions = ["submit_progress_report"] if is_main_assignee else []
        if can_report_issue:
            actions.append("report_task_issue")
        if (
            is_main_assignee
            and nodes
            and all(node.status == "completed" and node.progress_percent == 100 for node in nodes)
            and not has_non_closed_issue
            and not (
                latest_review is not None
                and latest_review.review_status == "rejected"
                and latest_review.rework_node_id is not None
                and not rework_node_reopened
            )
        ):
            actions.append("submit_completion")
    else:
        actions.extend(completion_review_allowed_actions(task, actor, current_review))
    if include_change_actions:
        actions.extend(
            _change_and_lifecycle_actions(
                task,
                actor,
                has_non_closed_issue=has_non_closed_issue,
                pending_change_request=pending_change_request,
            )
        )
    return list(dict.fromkeys(actions))


def _change_and_lifecycle_actions(
    task: Task,
    actor: str,
    *,
    has_non_closed_issue: bool,
    pending_change_request: TaskChangeRequest | None,
) -> list[str]:
    actions: list[str] = []
    if task.status == "in_progress" and actor == task.main_assignee_employee_no:
        if pending_change_request is None:
            actions.append("submit_change_request")
        else:
            actions.append("cancel_change_request")
    if pending_change_request is not None and actor == task.creator_employee_no:
        actions.extend(["approve_change_request", "reject_change_request"])
    if actor == task.creator_employee_no:
        if task.status in {
            "draft",
            "pending_confirmation",
            "pending_acceptance",
            "returned",
            "in_progress",
            "pending_review",
        }:
            actions.append("cancel_task")
        if (
            task.status in {"in_progress", "pending_review", "completed"}
            and not has_non_closed_issue
        ):
            actions.append("close_task")
        if task.status == "completed":
            actions.append("archive_task")
        if task.status in {"cancelled", "closed", "withdrawn", "archived"}:
            actions.append("restore_task")
        if task.status not in {"archived", "cancelled", "withdrawn", "merged"}:
            actions.append("merge_task")
    if actor == task.main_assignee_employee_no and task.status in {
        "pending_acceptance",
        "returned",
        "in_progress",
        "pending_review",
    }:
        actions.append("withdraw_task")
    return actions


def _node_actions(
    task: Task,
    node: TaskNode,
    actor: str,
    dependencies: list[TaskNodeDependency],
    nodes_by_id: dict[UUID, TaskNode],
    *,
    can_execute: bool,
    can_report: bool,
    has_active_blocker: bool,
    can_reopen: bool = False,
) -> list[str]:
    if task.status != "in_progress":
        return []
    if node.status == "completed" and can_reopen:
        return ["reopen_node"]
    if not can_execute and not can_report:
        return []
    shared_actions = ["submit_progress_report", "report_task_issue"] if can_report else []
    if node.status == "pending":
        predecessors = [
            nodes_by_id.get(item.predecessor_node_id)
            for item in dependencies
            if item.successor_node_id == node.node_id
        ]
        if can_execute and all(
            item is not None and item.status == "completed" for item in predecessors
        ):
            return ["start_node", *shared_actions]
        return shared_actions
    if node.status == "in_progress":
        actions = (["update_node_progress"] if can_execute else []) + shared_actions
        if can_execute and not has_active_blocker:
            actions.append("complete_node")
        return actions
    return []


class TaskBoardQueryService:
    def __init__(self, session: Session, clock=lambda: datetime.now(UTC)) -> None:
        self._session = session
        self._tasks = TaskRepository(session)
        self._nodes = TaskNodeRepository(session)
        self._users = UserRepository(session)
        self._reports = ProgressReportRepository(session)
        self._issues = TaskIssueRepository(session)
        self._completion_reviews = TaskCompletionReviewRepository(session)
        self._change_requests = TaskChangeRequestRepository(session)
        self._logs = TaskStatusLogRepository(session)
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

    def _review_context(
        self,
        task_id: UUID,
    ) -> tuple[
        TaskCompletionReview | None,
        TaskCompletionReview | None,
        bool,
    ]:
        current = self._completion_reviews.get_current_submitted(task_id)
        latest = self._completion_reviews.get_latest(task_id)
        reopened = True
        if (
            latest is not None
            and latest.review_status == "rejected"
            and latest.rework_node_id is not None
        ):
            reopened = self._logs.has_action_for_business_ref(
                task_id,
                "node_reopened",
                "completion_review",
                latest.completion_review_id,
                after_task_version=latest.reviewed_task_version,
            )
        return current, latest, reopened

    @staticmethod
    def _can_reopen_node(
        task: Task,
        node: TaskNode,
        actor: str,
        latest_review: TaskCompletionReview | None,
        rework_node_reopened: bool,
    ) -> bool:
        return (
            task.status == "in_progress"
            and node.status == "completed"
            and latest_review is not None
            and latest_review.review_status == "rejected"
            and latest_review.rework_node_id == node.node_id
            and latest_review.reviewer_employee_no == actor
            and not rework_node_reopened
        )

    def _inbox_task_candidates(self, actor: str) -> list[Task]:
        tasks = {task.task_id: task for task in self._tasks.list_inbox_candidates(actor)}
        reviews = [
            *self._completion_reviews.list_submitted_for_reviewer(actor),
            *self._completion_reviews.list_rejected_rework_candidates_for_reviewer(actor),
        ]
        for review in reviews:
            if review.task_id in tasks:
                continue
            task = self._tasks.get_by_id(review.task_id)
            if task is not None:
                tasks[task.task_id] = task
        for request in self._change_requests.list_pending(limit=500):
            if request.requester_employee_no != actor:
                task = self._tasks.get_by_id(request.task_id)
                if task is None or task.creator_employee_no != actor:
                    continue
            task = self._tasks.get_by_id(request.task_id)
            if task is not None:
                tasks[task.task_id] = task
        return sorted(
            tasks.values(),
            key=lambda task: (
                -_aware_utc(task.updated_at).timestamp(),
                str(task.task_id),
            ),
        )

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
        normalized_search = search.strip() if search and search.strip() else None
        if relation == "all":
            tasks, total = self._list_visible_tasks(
                actor,
                task_status=task_status,
                search=normalized_search,
                deadline_from=start,
                deadline_to=end,
                limit=limit,
                offset=offset,
            )
        else:
            tasks, total = self._tasks.list_related(
                actor,
                relation=relation,
                task_status=task_status,
                search=normalized_search,
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
        for task in self._inbox_task_candidates(actor):
            nodes, dependencies, task_participants, node_participants = self._context(task.task_id)
            current_review, latest_review, rework_node_reopened = self._review_context(task.task_id)
            pending_change_request = self._change_requests.get_pending(task.task_id)
            task_summary = self._summary(task, actor, context=(nodes, dependencies))
            task_actions = _task_actions(
                task,
                actor,
                nodes,
                has_non_closed_issue=self._issues.has_non_closed(task.task_id),
                is_task_participant=any(item.employee_no == actor for item in task_participants),
                current_review=current_review,
                latest_review=latest_review,
                rework_node_reopened=rework_node_reopened,
                pending_change_request=pending_change_request,
                include_change_actions=True,
            )
            if task.status == "pending_confirmation" and task_actions:
                actions = [
                    action
                    for action in task_actions
                    if action in {"confirm_and_send", "confirm_self_assigned"}
                ]
                if actions:
                    items.append(
                        self._inbox_item("confirm_task", task, task_summary, None, actions)
                    )
            elif task.status == "pending_acceptance" and task_actions:
                actions = [action for action in task_actions if action in {"accept", "return"}]
                if actions:
                    items.append(self._inbox_item("accept_task", task, task_summary, None, actions))
            elif task.status == "returned" and "resend" in task_actions:
                items.append(
                    self._inbox_item("handle_returned_task", task, task_summary, None, ["resend"])
                )
            elif task.status == "pending_review":
                review_actions = [
                    action
                    for action in task_actions
                    if action in {"approve_completion", "reject_completion"}
                ]
                if review_actions:
                    items.append(
                        self._inbox_item(
                            "approve_completion", task, task_summary, None, review_actions
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
                    node_actions = _node_actions(
                        task,
                        node,
                        actor,
                        dependencies,
                        nodes_by_id,
                        can_execute=self._node_can_execute(
                            task, node, actor, node_participants
                        ),
                        can_report=self._node_can_report(
                            task, node, actor, node_participants
                        ),
                        has_active_blocker=self._issues.has_active_blocker(
                            task.task_id, node.node_id
                        ),
                        can_reopen=self._can_reopen_node(
                            task, node, actor, latest_review, rework_node_reopened
                        ),
                    )
                    for action in node_actions:
                        if action in {"submit_progress_report", "report_task_issue"}:
                            continue
                        code = "update_node" if action == "update_node_progress" else action
                        items.append(self._inbox_item(code, task, task_summary, node, [action]))
                _, period_end = task_report_period(
                    task.report_cycle,
                    task.accepted_at,
                    _aware_utc(self._clock()),
                )
                if (
                    actor == task.main_assignee_employee_no
                    and period_end is not None
                    and period_end <= _aware_utc(self._clock())
                    and not self._reports.has_root_task_report_for_period(task.task_id, period_end)
                ):
                    items.append(
                        {
                            "inbox_item_type": "report_due",
                            "action_code": "report_due",
                            "task": task_summary,
                            "node": None,
                            "reason": "Periodic task progress report is due.",
                            "expected_task_version": task.task_version,
                            "endpoint": f"/api/v1/tasks/{task.task_id}/progress-reports",
                            "allowed_actions": ["submit_progress_report"],
                            "is_overdue": True,
                            "relevant_at": period_end,
                        }
                    )

            if pending_change_request is not None:
                if actor == task.creator_employee_no:
                    request_endpoint = (
                        f"/api/v1/tasks/{task.task_id}/change-requests/"
                        f"{pending_change_request.change_request_id}/actions"
                    )
                    for action, suffix, reason in (
                        (
                            "approve_change_request",
                            "approve",
                            "A task change request is waiting for creator approval.",
                        ),
                        (
                            "reject_change_request",
                            "reject",
                            "A task change request is waiting for creator review.",
                        ),
                    ):
                        items.append(
                            self._change_request_inbox_item(
                                action,
                                task,
                                task_summary,
                                pending_change_request,
                                f"{request_endpoint}/{suffix}",
                                reason,
                            )
                        )
                if actor == pending_change_request.requester_employee_no:
                    items.append(
                        self._change_request_inbox_item(
                            "cancel_change_request",
                            task,
                            task_summary,
                            pending_change_request,
                            (
                                f"/api/v1/tasks/{task.task_id}/change-requests/"
                                f"{pending_change_request.change_request_id}/actions/cancel"
                            ),
                            "Your pending task change request can be cancelled.",
                        )
                    )
        for issue in self._issues.list_actionable_for(actor):
            task = self._tasks.get_by_id(issue.task_id)
            if task is None:
                continue
            nodes, dependencies, _, _ = self._context(task.task_id)
            node = next((item for item in nodes if item.node_id == issue.node_id), None)
            task_summary = self._summary(task, actor, context=(nodes, dependencies))
            actions = [f"{action}_issue" for action in issue_allowed_actions(issue, actor)]
            if not actions:
                continue
            items.append(
                {
                    "inbox_item_type": "task_issue",
                    "action_code": "handle_issue",
                    "task": task_summary,
                    "node": self._node_summary(node) if node is not None else None,
                    "reason": f"{issue.severity} {issue.issue_type}: {issue.title}",
                    "expected_task_version": task.task_version,
                    "endpoint": (f"/api/v1/tasks/{task.task_id}/issues/{issue.issue_id}/actions"),
                    "allowed_actions": actions,
                    "is_overdue": task_summary["is_overdue"],
                    "relevant_at": issue.created_at,
                }
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
        if not PermissionScopeService(self._session).can_access_task(actor, task):
            raise PermissionDeniedError("actor cannot read this task")
        nodes, dependencies, task_participants, node_participants = self._context(task_id)
        current_review, latest_review, rework_node_reopened = self._review_context(task_id)
        nodes_by_id = {node.node_id: node for node in nodes}
        return {
            "task_id": task.task_id,
            "task_version": task.task_version,
            "allowed_actions": _task_actions(
                task,
                actor,
                nodes,
                has_non_closed_issue=self._issues.has_non_closed(task.task_id),
                is_task_participant=any(item.employee_no == actor for item in task_participants),
                current_review=current_review,
                latest_review=latest_review,
                rework_node_reopened=rework_node_reopened,
                pending_change_request=self._change_requests.get_pending(task.task_id),
                include_change_actions=True,
            ),
            "nodes": [
                {
                    "node_id": node.node_id,
                    "allowed_actions": _node_actions(
                        task,
                        node,
                        actor,
                        dependencies,
                        nodes_by_id,
                        can_execute=self._node_can_execute(
                            task,
                            node,
                            actor,
                            node_participants,
                        ),
                        can_report=self._node_can_report(
                            task,
                            node,
                            actor,
                            node_participants,
                        ),
                        has_active_blocker=self._issues.has_active_blocker(
                            task.task_id,
                            node.node_id,
                        ),
                        can_reopen=self._can_reopen_node(
                            task,
                            node,
                            actor,
                            latest_review,
                            rework_node_reopened,
                        ),
                    ),
                }
                for node in nodes
            ],
        }

    def _list_visible_tasks(
        self,
        actor: str,
        *,
        task_status: str | None,
        search: str | None,
        deadline_from: datetime | None,
        deadline_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]:
        permission = PermissionScopeService(self._session)
        statement = select(Task)
        if task_status is not None:
            statement = statement.where(Task.status == task_status)
        if search:
            statement = statement.where(Task.task_name.contains(search, autoescape=True))
        if deadline_from is not None:
            statement = statement.where(Task.deadline >= deadline_from)
        if deadline_to is not None:
            statement = statement.where(Task.deadline < deadline_to)
        statement = statement.order_by(
            func.coalesce(Task.is_urgent, false()).desc(),
            Task.deadline.asc().nulls_last(),
            Task.created_at.desc(),
            Task.task_id,
        )
        visible = [
            task
            for task in self._session.scalars(statement).all()
            if permission.can_access_task(actor, task)
        ]
        return visible[offset : offset + limit], len(visible)

    def dashboard_summary(self, actor: str) -> dict[str, object]:
        now = _aware_utc(self._clock())
        today_start = datetime.combine(now.date(), time.min, UTC)
        tomorrow_start = today_start + timedelta(days=1)
        due_end = now + timedelta(days=DUE_WINDOW_DAYS)
        recent = self._tasks.list_recent_related(actor, limit=5)
        inbox = self.list_inbox(actor, action_code=None, limit=500, offset=0)
        inbox_items = list(inbox["items"])
        report_due_count = len(
            [item for item in inbox_items if item["action_code"] == "report_due"]
        )
        completion_review_count = len(
            [item for item in inbox_items if item["action_code"] == "approve_completion"]
        )
        open_issue_count = self._issues.count_open_owned_by(actor)
        return {
            "created_task_count": self._tasks.count_related(actor, relation="created"),
            "assigned_task_count": self._tasks.count_related(actor, relation="assigned"),
            "inbox_count": inbox["total"],
            "in_progress_count": self._tasks.count_related(actor, task_status="in_progress"),
            "pending_acceptance_count": self._tasks.count_related(
                actor,
                relation="assigned",
                task_status="pending_acceptance",
            ),
            "today_task_count": self._tasks.count_related(
                actor,
                deadline_from=today_start,
                deadline_to=tomorrow_start,
                exclude_completed=True,
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
            "report_due_count": report_due_count,
            "open_issue_count": open_issue_count,
            "blocked_task_count": open_issue_count,
            "completion_review_count": completion_review_count,
            "unread_notification_count": self._unread_notification_count(actor),
            "open_conflict_count": self._open_conflict_count(actor),
            "due_window_days": DUE_WINDOW_DAYS,
            "recent_tasks": [self._summary(task, actor) for task in recent],
            "latest_workload": self._latest_workload(actor),
            "priority_items": self._priority_items(actor),
        }

    def _unread_notification_count(self, actor: str) -> int:
        return int(
            self._session.execute(
                select(func.count()).select_from(Notification).where(
                    Notification.recipient_employee_no == actor,
                    Notification.read_at.is_(None),
                )
            ).scalar_one()
            or 0
        )

    def _open_conflict_count(self, actor: str) -> int:
        return int(
            self._session.execute(
                select(func.count()).select_from(TaskConflict).where(
                    TaskConflict.employee_no == actor,
                    TaskConflict.status == "open",
                )
            ).scalar_one()
            or 0
        )

    def _latest_workload(self, actor: str) -> dict[str, object] | None:
        row = self._session.execute(
            select(WorkloadSnapshot)
            .where(WorkloadSnapshot.employee_no == actor)
            .order_by(WorkloadSnapshot.calculated_at.desc(), WorkloadSnapshot.workload_snapshot_id)
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "workload_snapshot_id": row.workload_snapshot_id,
            "workload_score": row.workload_score,
            "workload_level": row.workload_level,
            "calculated_at": row.calculated_at,
        }

    def _priority_items(self, actor: str) -> list[dict[str, object]]:
        task_ids = [task.task_id for task in self._tasks.list_related(actor, limit=500)[0]]
        if not task_ids:
            return []
        rows = list(
            self._session.scalars(
                select(TaskPriorityScore)
                .where(TaskPriorityScore.task_id.in_(task_ids))
                .order_by(
                    TaskPriorityScore.sort_rank.asc().nulls_last(),
                    TaskPriorityScore.calculated_at.desc(),
                    TaskPriorityScore.task_id,
                )
                .limit(10)
            ).all()
        )
        latest_by_task: dict[UUID, TaskPriorityScore] = {}
        for row in rows:
            latest_by_task.setdefault(row.task_id, row)
        return [
            {
                "task_id": row.task_id,
                "priority_quadrant": row.priority_quadrant,
                "importance_score": row.importance_score,
                "urgency_score": row.urgency_score,
                "sort_rank": row.sort_rank,
                "calculated_at": row.calculated_at,
            }
            for row in latest_by_task.values()
        ]

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
        current_review, latest_review, rework_node_reopened = self._review_context(task.task_id)
        employee_nos = tuple(
            item
            for item in {task.creator_employee_no, task.main_assignee_employee_no}
            if item is not None
        )
        people = {item.employee_no: item for item in self._users.list_by_employee_nos(employee_nos)}
        creator = people.get(task.creator_employee_no)
        assignee = (
            people.get(task.main_assignee_employee_no) if task.main_assignee_employee_no else None
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
        if self._issues.has_employee_relation(task.task_id, actor):
            relations.append("issue_participant")
        if latest_review is not None:
            if latest_review.submitted_by_employee_no == actor:
                relations.append("completion_submitter")
            if latest_review.reviewer_employee_no == actor:
                relations.append("completion_reviewer")
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
            "allowed_actions": _task_actions(
                task,
                actor,
                nodes,
                has_non_closed_issue=self._issues.has_non_closed(task.task_id),
                is_task_participant=any(item.employee_no == actor for item in participants),
                current_review=current_review,
                latest_review=latest_review,
                rework_node_reopened=rework_node_reopened,
                pending_change_request=self._change_requests.get_pending(task.task_id),
                include_change_actions=True,
            ),
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
            "reopen_node": "reopen",
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
            "reopen_node": "A rejected completion review requires an explicit node reopen.",
        }[action_code]
        return {
            "inbox_item_type": action_code,
            "action_code": action_code,
            "task": task_summary,
            "node": self._node_summary(node) if node is not None else None,
            "reason": reason,
            "expected_task_version": task.task_version,
            "endpoint": endpoint,
            "allowed_actions": allowed_actions,
            "is_overdue": task_summary["is_overdue"],
            "relevant_at": task.updated_at,
        }

    @staticmethod
    def _change_request_inbox_item(
        action_code: str,
        task: Task,
        task_summary: dict[str, object],
        request: TaskChangeRequest,
        endpoint: str,
        reason: str,
    ) -> dict[str, object]:
        return {
            "inbox_item_type": "task_change_request",
            "action_code": action_code,
            "task": task_summary,
            "node": None,
            "reason": reason,
            "expected_task_version": task.task_version,
            "endpoint": endpoint,
            "allowed_actions": [action_code],
            "is_overdue": task_summary["is_overdue"],
            "relevant_at": request.created_at,
        }

    @staticmethod
    def _node_summary(node: TaskNode) -> dict[str, object]:
        return {
            "node_id": node.node_id,
            "node_name": node.node_name,
            "status": node.status,
            "progress_percent": node.progress_percent,
            "owner_employee_no": node.owner_employee_no,
        }

    @staticmethod
    def _node_can_execute(
        task: Task,
        node: TaskNode,
        actor: str,
        node_participants: list[TaskNodeParticipant],
    ) -> bool:
        if actor in {task.main_assignee_employee_no, node.owner_employee_no}:
            return True
        return any(
            item.node_id == node.node_id
            and item.employee_no == actor
            and item.participant_role == "owner"
            for item in node_participants
        )

    @staticmethod
    def _node_can_report(
        task: Task,
        node: TaskNode,
        actor: str,
        node_participants: list[TaskNodeParticipant],
    ) -> bool:
        if actor in {task.main_assignee_employee_no, node.owner_employee_no}:
            return True
        return any(
            item.node_id == node.node_id
            and item.employee_no == actor
            and item.participant_role in {"owner", "collaborator"}
            for item in node_participants
        )
