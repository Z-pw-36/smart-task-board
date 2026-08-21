from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


def _utc_now() -> datetime:
    return datetime.now(UTC)


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"
    __table_args__ = (
        CheckConstraint(
            "daily_capacity_hours >= 0", name="ck_employee_profiles_capacity_non_negative"
        ),
        CheckConstraint(
            "standard_task_count >= 1", name="ck_employee_profiles_task_count_positive"
        ),
        CheckConstraint(
            "standard_task_weight >= 1 AND standard_task_weight <= 5",
            name="ck_employee_profiles_task_weight_range",
        ),
        CheckConstraint(
            "emergency_tolerance_count >= 0", name="ck_employee_profiles_emergency_non_negative"
        ),
        CheckConstraint(
            "availability_status IN ('available', 'busy', 'unavailable', 'disabled')",
            name="ck_employee_profiles_availability_status",
        ),
    )

    employee_no: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT"), primary_key=True
    )
    responsibility_text: Mapped[str | None] = mapped_column(Text)
    skill_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    daily_capacity_hours: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=8)
    standard_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    standard_task_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    emergency_tolerance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    availability_status: Mapped[str] = mapped_column(String, nullable=False, default="available")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    employee: Mapped[User] = relationship(
        back_populates="employee_profile",
        foreign_keys=[employee_no],
    )


class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"
    __table_args__ = (
        CheckConstraint(
            "weight IS NULL OR weight >= 0", name="ck_performance_metrics_weight_non_negative"
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')", name="ck_performance_metrics_status"
        ),
        Index("ix_performance_metrics_scope_status", "business_unit", "status"),
        Index("ix_performance_metrics_name", "metric_name"),
    )

    metric_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    metric_type: Mapped[str] = mapped_column(String, nullable=False)
    period: Mapped[str | None] = mapped_column(String)
    business_unit: Mapped[str | None] = mapped_column(String)
    sequence_no: Mapped[int | None] = mapped_column(Integer)
    dimension: Mapped[str | None] = mapped_column(String)
    metric_name: Mapped[str] = mapped_column(String, nullable=False)
    definition_formula: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[Decimal | None] = mapped_column(Numeric)
    target_value: Mapped[str | None] = mapped_column(String)
    deliverable: Mapped[str | None] = mapped_column(Text)
    data_source: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class TaskPerformanceMatch(Base):
    __tablename__ = "task_performance_matches"
    __table_args__ = (
        UniqueConstraint("task_id", "metric_id", name="uq_task_performance_matches_task_metric"),
        CheckConstraint(
            "type_score >= 0 AND type_score <= 100", name="ck_task_performance_matches_type_score"
        ),
        CheckConstraint(
            "business_unit_score >= 0 AND business_unit_score <= 100",
            name="ck_task_performance_matches_business_unit_score",
        ),
        CheckConstraint(
            "metric_name_score >= 0 AND metric_name_score <= 100",
            name="ck_task_performance_matches_metric_name_score",
        ),
        CheckConstraint(
            "definition_formula_score >= 0 AND definition_formula_score <= 100",
            name="ck_task_performance_matches_definition_formula_score",
        ),
        CheckConstraint(
            "deliverable_score >= 0 AND deliverable_score <= 100",
            name="ck_task_performance_matches_deliverable_score",
        ),
        CheckConstraint(
            "total_score >= 0 AND total_score <= 100",
            name="ck_task_performance_matches_total_score",
        ),
        CheckConstraint(
            "match_level IN ('strong', 'weak', 'no_clear_relation')",
            name="ck_task_performance_matches_level",
        ),
        Index(
            "ix_task_performance_matches_task_confirmation",
            "task_id",
            "is_confirmed",
            "total_score",
        ),
    )

    performance_match_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.task_id", ondelete="RESTRICT"), nullable=False
    )
    metric_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("performance_metrics.metric_id", ondelete="RESTRICT"),
        nullable=False,
    )
    type_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    business_unit_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    metric_name_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    definition_formula_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    deliverable_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    total_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    match_level: Mapped[str] = mapped_column(
        String, nullable=False, default="no_clear_relation"
    )
    match_reason: Mapped[str | None] = mapped_column(Text)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_by_employee_no: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    algorithm_version: Mapped[str] = mapped_column(String, nullable=False, default="v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class WorkloadSnapshot(Base):
    __tablename__ = "workload_snapshots"
    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="ck_workload_snapshots_period_order"),
        CheckConstraint(
            "remaining_hours_sum >= 0", name="ck_workload_snapshots_remaining_hours_non_negative"
        ),
        CheckConstraint(
            "available_hours >= 0", name="ck_workload_snapshots_available_hours_non_negative"
        ),
        CheckConstraint(
            "workload_score >= 0 AND workload_score <= 100",
            name="ck_workload_snapshots_score_range",
        ),
        Index("ix_workload_snapshots_employee_period", "employee_no", "period_start", "period_end"),
    )

    workload_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    employee_no: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remaining_hours_sum: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    available_hours: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    active_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_task_weight_sum: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    urgent_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hours_pressure: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    weight_pressure: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    count_pressure: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    urgent_pressure: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    blocked_overdue_pressure: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    workload_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    workload_level: Mapped[str] = mapped_column(String, nullable=False, default="idle")
    parameter_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class TaskPriorityScore(Base):
    __tablename__ = "task_priority_scores"
    __table_args__ = (
        CheckConstraint(
            "importance_score >= 0 AND importance_score <= 100",
            name="ck_task_priority_scores_importance_range",
        ),
        CheckConstraint(
            "urgency_score >= 0 AND urgency_score <= 100",
            name="ck_task_priority_scores_urgency_range",
        ),
        Index("ix_task_priority_scores_task_calculated", "task_id", "calculated_at"),
    )

    priority_score_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.task_id", ondelete="RESTRICT"), nullable=False
    )
    task_weight_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    performance_match_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    report_to_level_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    importance_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    time_pressure_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    overdue_pressure_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    urgent_pressure_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    urgency_score: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    priority_quadrant: Mapped[str] = mapped_column(String, nullable=False)
    remaining_hours: Mapped[Decimal | None] = mapped_column(Numeric)
    sort_rank: Mapped[int | None] = mapped_column(Integer)
    task_created_at_snapshot: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    explanation: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class TaskConflict(Base):
    __tablename__ = "task_conflicts"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_task_conflicts_dedupe_key"),
        CheckConstraint(
            "conflict_type IN "
            "('work_hour', 'deadline_concentration', 'dependency', 'emergency_displacement')",
            name="ck_task_conflicts_type",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_task_conflicts_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'ignored', 'resolved')",
            name="ck_task_conflicts_status",
        ),
        Index("ix_task_conflicts_employee_status", "employee_no", "status", "severity"),
    )

    conflict_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    conflict_type: Mapped[str] = mapped_column(String, nullable=False)
    employee_no: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.task_id", ondelete="RESTRICT"), nullable=False
    )
    related_task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.task_id", ondelete="RESTRICT")
    )
    node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_nodes.node_id", ondelete="RESTRICT")
    )
    dedupe_key: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    resolved_by_employee_no: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT")
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReminderRule(Base):
    __tablename__ = "reminder_rules"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_reminder_rules_dedupe_key"),
        CheckConstraint(
            "reminder_type IN ("
            "'pending_acceptance', 'due_soon', 'due_today', 'overdue', "
            "'periodic_progress_report', 'pending_report', 'no_response', "
            "'issue_blocker', 'collaboration', 'returned', 'completion_review', "
            "'change_request')",
            name="ck_reminder_rules_type",
        ),
        Index("ix_reminder_rules_due", "is_active", "next_trigger_at"),
    )

    reminder_rule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.task_id", ondelete="RESTRICT")
    )
    node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_nodes.node_id", ondelete="RESTRICT")
    )
    issue_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_issues.issue_id", ondelete="RESTRICT")
    )
    reminder_type: Mapped[str] = mapped_column(String, nullable=False)
    recipient_employee_no: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT"), nullable=False
    )
    trigger_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_trigger_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    repeat_rule: Mapped[str | None] = mapped_column(String)
    dedupe_key: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "dedupe_key",
            "channel",
            "recipient_employee_no",
            name="uq_notifications_dedupe_recipient_channel",
        ),
        CheckConstraint(
            "send_status IN ('pending', 'sent', 'failed', 'cancelled')",
            name="ck_notifications_send_status",
        ),
        CheckConstraint("retry_count >= 0", name="ck_notifications_retry_count"),
        Index(
            "ix_notifications_recipient_status",
            "recipient_employee_no",
            "send_status",
            "created_at",
        ),
    )

    notification_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    reminder_rule_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("reminder_rules.reminder_rule_id", ondelete="RESTRICT")
    )
    task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.task_id", ondelete="RESTRICT")
    )
    issue_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_issues.issue_id", ondelete="RESTRICT")
    )
    recipient_employee_no: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String, nullable=False, default="in_app")
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    send_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    wecom_message_id: Mapped[str | None] = mapped_column(String)
    fail_reason: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class TaskArchive(Base):
    __tablename__ = "task_archives"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_task_archives_task"),
        Index("ix_task_archives_keywords", "search_keywords", postgresql_using="gin"),
    )

    archive_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tasks.task_id", ondelete="RESTRICT"), nullable=False
    )
    archive_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_status_snapshot: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    search_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    review_result: Mapped[str | None] = mapped_column(String)
    risk_points: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    reusable_template: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    actual_hours_total: Mapped[Decimal | None] = mapped_column(Numeric)
    archived_by_employee_no: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT"), nullable=False
    )
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class OperationLog(Base):
    __tablename__ = "operation_logs"
    __table_args__ = (
        Index("ix_operation_logs_request", "request_id"),
        Index("ix_operation_logs_object", "object_type", "object_id", "created_at"),
        Index("ix_operation_logs_operator", "operator_employee_no", "created_at"),
    )

    operation_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    request_id: Mapped[str | None] = mapped_column(String)
    operator_employee_no: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    object_type: Mapped[str] = mapped_column(String, nullable=False)
    object_id: Mapped[str] = mapped_column(String, nullable=False)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String)
    user_agent: Mapped[str | None] = mapped_column(String)
    result: Mapped[str] = mapped_column(String, nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class UserAuthorizedScope(Base):
    __tablename__ = "user_authorized_scopes"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_user_authorized_scopes_validity",
        ),
        CheckConstraint(
            "scope_type IN ('department', 'user', 'role', 'all_demo_data')",
            name="ck_user_authorized_scopes_scope_type",
        ),
        CheckConstraint(
            "permission_type IN ('view', 'manage', 'export')",
            name="ck_user_authorized_scopes_permission_type",
        ),
        CheckConstraint(
            "status IN ('active', 'expired', 'disabled')",
            name="ck_user_authorized_scopes_status",
        ),
        Index("ix_user_authorized_scopes_active", "employee_no", "status", "scope_type"),
    )

    authorized_scope_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    employee_no: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT"), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String, nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String)
    permission_type: Mapped[str] = mapped_column(String, nullable=False, default="view")
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_by_employee_no: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class SystemParameter(Base):
    __tablename__ = "system_parameters"
    __table_args__ = (
        UniqueConstraint("param_key", name="uq_system_parameters_key"),
        CheckConstraint(
            "param_type IN ('number', 'string', 'boolean', 'json')",
            name="ck_system_parameters_type",
        ),
        Index("ix_system_parameters_module_active", "module", "is_active"),
    )

    parameter_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    param_key: Mapped[str] = mapped_column(String, nullable=False)
    param_name: Mapped[str] = mapped_column(String, nullable=False)
    param_value: Mapped[str] = mapped_column(Text, nullable=False)
    param_type: Mapped[str] = mapped_column(String, nullable=False, default="number")
    module: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_employee_no: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class RefreshToken(Base):
    """Rotating, revocable refresh-token family record.

    Only a SHA-256 digest is persisted; the bearer value is returned once.
    """

    __tablename__ = "auth_refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_hash"),
        Index(
            "ix_auth_refresh_tokens_employee_status",
            "employee_no",
            "status",
            "expires_at",
        ),
        CheckConstraint(
            "status IN ('active', 'rotated', 'revoked', 'expired')",
            name="ck_auth_refresh_tokens_status",
        ),
    )

    refresh_token_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    employee_no: Mapped[str] = mapped_column(
        String, ForeignKey("users.employee_no", ondelete="RESTRICT"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    family_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_token_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth_refresh_tokens.refresh_token_id", ondelete="RESTRICT"),
    )
    client_id: Mapped[str | None] = mapped_column(String)
    user_agent: Mapped[str | None] = mapped_column(String)
