"""
Feature: Task detail read-only performance projection.

Responsibilities:
- Load confirmed performance matches for a task detail response.
- Keep metric joins out of route and service presentation code.

Does not own: KPI scoring, confirmation writes, or permission decisions.
Plan task: DEV-05.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PerformanceMetric, TaskPerformanceMatch


class TaskPerformanceMatchRepository:
    """Read confirmed task-performance matches with their metric display fields."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_confirmed_by_task_id(
        self,
        task_id: UUID,
        *,
        limit: int = 10,
    ) -> list[tuple[TaskPerformanceMatch, PerformanceMetric]]:
        statement = (
            select(TaskPerformanceMatch, PerformanceMetric)
            .join(
                PerformanceMetric,
                PerformanceMetric.metric_id == TaskPerformanceMatch.metric_id,
            )
            .where(
                TaskPerformanceMatch.task_id == task_id,
                TaskPerformanceMatch.is_confirmed.is_(True),
            )
            .order_by(
                TaskPerformanceMatch.total_score.desc(),
                TaskPerformanceMatch.confirmed_at.desc().nulls_last(),
                TaskPerformanceMatch.performance_match_id,
            )
            .limit(limit)
        )
        return list(self.session.execute(statement).all())
