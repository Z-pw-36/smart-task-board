"""add remaining SmartTaskBoard business tables

Revision ID: e6f1a2b3c4d5
Revises: d4a8e53b7c19
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e6f1a2b3c4d5"
down_revision: str | Sequence[str] | None = "d4a8e53b7c19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    seeded_at = datetime.now(UTC)

    op.create_table(
        "employee_profiles",
        sa.Column("employee_no", sa.String(), nullable=False),
        sa.Column("responsibility_text", sa.Text(), nullable=True),
        sa.Column("skill_tags", JSONB, nullable=False),
        sa.Column("daily_capacity_hours", sa.Numeric(), nullable=False),
        sa.Column("standard_task_count", sa.Integer(), nullable=False),
        sa.Column("standard_task_weight", sa.Integer(), nullable=False),
        sa.Column("emergency_tolerance_count", sa.Integer(), nullable=False),
        sa.Column("availability_status", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "daily_capacity_hours >= 0", name="ck_employee_profiles_capacity_non_negative"
        ),
        sa.CheckConstraint(
            "standard_task_count >= 1", name="ck_employee_profiles_task_count_positive"
        ),
        sa.CheckConstraint(
            "standard_task_weight >= 1 AND standard_task_weight <= 5",
            name="ck_employee_profiles_task_weight_range",
        ),
        sa.CheckConstraint(
            "emergency_tolerance_count >= 0", name="ck_employee_profiles_emergency_non_negative"
        ),
        sa.CheckConstraint(
            "availability_status IN ('available', 'busy', 'unavailable', 'disabled')",
            name="ck_employee_profiles_availability_status",
        ),
        sa.ForeignKeyConstraint(
            ["employee_no"],
            ["users.employee_no"],
            name=op.f("fk_employee_profiles_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("employee_no", name=op.f("pk_employee_profiles")),
    )
    op.create_table(
        "performance_metrics",
        sa.Column("metric_id", sa.Uuid(), nullable=False),
        sa.Column("metric_type", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=True),
        sa.Column("business_unit", sa.String(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.Column("dimension", sa.String(), nullable=True),
        sa.Column("metric_name", sa.String(), nullable=False),
        sa.Column("definition_formula", sa.Text(), nullable=True),
        sa.Column("weight", sa.Numeric(), nullable=True),
        sa.Column("target_value", sa.String(), nullable=True),
        sa.Column("deliverable", sa.Text(), nullable=True),
        sa.Column("data_source", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "weight IS NULL OR weight >= 0", name="ck_performance_metrics_weight_non_negative"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')", name="ck_performance_metrics_status"
        ),
        sa.PrimaryKeyConstraint("metric_id", name=op.f("pk_performance_metrics")),
    )
    op.create_index(
        "ix_performance_metrics_scope_status", "performance_metrics", ["business_unit", "status"]
    )
    op.create_index("ix_performance_metrics_name", "performance_metrics", ["metric_name"])
    op.create_table(
        "task_performance_matches",
        sa.Column("performance_match_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("metric_id", sa.Uuid(), nullable=False),
        sa.Column("type_score", sa.Numeric(), nullable=False),
        sa.Column("business_unit_score", sa.Numeric(), nullable=False),
        sa.Column("metric_name_score", sa.Numeric(), nullable=False),
        sa.Column("definition_formula_score", sa.Numeric(), nullable=False),
        sa.Column("deliverable_score", sa.Numeric(), nullable=False),
        sa.Column("total_score", sa.Numeric(), nullable=False),
        sa.Column("match_level", sa.String(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("confirmed_by_employee_no", sa.String(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("algorithm_version", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type_score >= 0 AND type_score <= 100",
            name="ck_task_performance_matches_type_score",
        ),
        sa.CheckConstraint(
            "business_unit_score >= 0 AND business_unit_score <= 100",
            name="ck_task_performance_matches_business_unit_score",
        ),
        sa.CheckConstraint(
            "metric_name_score >= 0 AND metric_name_score <= 100",
            name="ck_task_performance_matches_metric_name_score",
        ),
        sa.CheckConstraint(
            "definition_formula_score >= 0 AND definition_formula_score <= 100",
            name="ck_task_performance_matches_definition_formula_score",
        ),
        sa.CheckConstraint(
            "deliverable_score >= 0 AND deliverable_score <= 100",
            name="ck_task_performance_matches_deliverable_score",
        ),
        sa.CheckConstraint(
            "total_score >= 0 AND total_score <= 100",
            name="ck_task_performance_matches_total_score",
        ),
        sa.CheckConstraint(
            "match_level IN ('strong', 'weak', 'no_clear_relation')",
            name="ck_task_performance_matches_level",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_task_performance_matches_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["metric_id"],
            ["performance_metrics.metric_id"],
            name=op.f("fk_task_performance_matches_metric_id_performance_metrics"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_performance_matches_confirmed_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("performance_match_id", name=op.f("pk_task_performance_matches")),
        sa.UniqueConstraint("task_id", "metric_id", name="uq_task_performance_matches_task_metric"),
    )
    op.create_index(
        "ix_task_performance_matches_task_confirmation",
        "task_performance_matches",
        ["task_id", "is_confirmed", "total_score"],
    )
    op.create_table(
        "workload_snapshots",
        sa.Column("workload_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("employee_no", sa.String(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remaining_hours_sum", sa.Numeric(), nullable=False),
        sa.Column("available_hours", sa.Numeric(), nullable=False),
        sa.Column("active_task_count", sa.Integer(), nullable=False),
        sa.Column("active_task_weight_sum", sa.Numeric(), nullable=False),
        sa.Column("urgent_task_count", sa.Integer(), nullable=False),
        sa.Column("blocked_task_count", sa.Integer(), nullable=False),
        sa.Column("overdue_task_count", sa.Integer(), nullable=False),
        sa.Column("hours_pressure", sa.Numeric(), nullable=False),
        sa.Column("weight_pressure", sa.Numeric(), nullable=False),
        sa.Column("count_pressure", sa.Numeric(), nullable=False),
        sa.Column("urgent_pressure", sa.Numeric(), nullable=False),
        sa.Column("blocked_overdue_pressure", sa.Numeric(), nullable=False),
        sa.Column("workload_score", sa.Numeric(), nullable=False),
        sa.Column("workload_level", sa.String(), nullable=False),
        sa.Column("parameter_snapshot", JSONB, nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("period_end >= period_start", name="ck_workload_snapshots_period_order"),
        sa.CheckConstraint(
            "remaining_hours_sum >= 0", name="ck_workload_snapshots_remaining_hours_non_negative"
        ),
        sa.CheckConstraint(
            "available_hours >= 0", name="ck_workload_snapshots_available_hours_non_negative"
        ),
        sa.CheckConstraint(
            "workload_score >= 0 AND workload_score <= 100",
            name="ck_workload_snapshots_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["employee_no"],
            ["users.employee_no"],
            name=op.f("fk_workload_snapshots_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("workload_snapshot_id", name=op.f("pk_workload_snapshots")),
    )
    op.create_index(
        "ix_workload_snapshots_employee_period",
        "workload_snapshots",
        ["employee_no", "period_start", "period_end"],
    )
    op.create_table(
        "task_priority_scores",
        sa.Column("priority_score_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("task_weight_score", sa.Numeric(), nullable=False),
        sa.Column("performance_match_score", sa.Numeric(), nullable=False),
        sa.Column("report_to_level_score", sa.Numeric(), nullable=False),
        sa.Column("importance_score", sa.Numeric(), nullable=False),
        sa.Column("time_pressure_score", sa.Numeric(), nullable=False),
        sa.Column("overdue_pressure_score", sa.Numeric(), nullable=False),
        sa.Column("urgent_pressure_score", sa.Numeric(), nullable=False),
        sa.Column("urgency_score", sa.Numeric(), nullable=False),
        sa.Column("priority_quadrant", sa.String(), nullable=False),
        sa.Column("remaining_hours", sa.Numeric(), nullable=True),
        sa.Column("sort_rank", sa.Integer(), nullable=True),
        sa.Column("task_created_at_snapshot", sa.DateTime(timezone=True), nullable=False),
        sa.Column("explanation", JSONB, nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "importance_score >= 0 AND importance_score <= 100",
            name="ck_task_priority_scores_importance_range",
        ),
        sa.CheckConstraint(
            "urgency_score >= 0 AND urgency_score <= 100",
            name="ck_task_priority_scores_urgency_range",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_task_priority_scores_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("priority_score_id", name=op.f("pk_task_priority_scores")),
    )
    op.create_index(
        "ix_task_priority_scores_task_calculated",
        "task_priority_scores",
        ["task_id", "calculated_at"],
    )
    op.create_table(
        "task_conflicts",
        sa.Column("conflict_id", sa.Uuid(), nullable=False),
        sa.Column("conflict_type", sa.String(), nullable=False),
        sa.Column("employee_no", sa.String(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("related_task_id", sa.Uuid(), nullable=True),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("resolved_by_employee_no", sa.String(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "conflict_type IN "
            "('work_hour', 'deadline_concentration', 'dependency', 'emergency_displacement')",
            name="ck_task_conflicts_type",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_task_conflicts_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'ignored', 'resolved')",
            name="ck_task_conflicts_status",
        ),
        sa.ForeignKeyConstraint(
            ["employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_conflicts_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_task_conflicts_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["related_task_id"],
            ["tasks.task_id"],
            name=op.f("fk_task_conflicts_related_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["task_nodes.node_id"],
            name=op.f("fk_task_conflicts_node_id_task_nodes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_conflicts_resolved_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("conflict_id", name=op.f("pk_task_conflicts")),
        sa.UniqueConstraint("dedupe_key", name="uq_task_conflicts_dedupe_key"),
    )
    op.create_index(
        "ix_task_conflicts_employee_status", "task_conflicts", ["employee_no", "status", "severity"]
    )
    op.create_table(
        "reminder_rules",
        sa.Column("reminder_rule_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("issue_id", sa.Uuid(), nullable=True),
        sa.Column("reminder_type", sa.String(), nullable=False),
        sa.Column("recipient_employee_no", sa.String(), nullable=False),
        sa.Column("trigger_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_trigger_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("repeat_rule", sa.String(), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reminder_type IN ("
            "'pending_acceptance', 'due_soon', 'due_today', 'overdue', "
            "'periodic_progress_report', 'pending_report', 'no_response', "
            "'issue_blocker', 'collaboration', 'returned', 'completion_review', "
            "'change_request')",
            name="ck_reminder_rules_type",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_reminder_rules_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["task_nodes.node_id"],
            name=op.f("fk_reminder_rules_node_id_task_nodes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["task_issues.issue_id"],
            name=op.f("fk_reminder_rules_issue_id_task_issues"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_reminder_rules_recipient_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("reminder_rule_id", name=op.f("pk_reminder_rules")),
        sa.UniqueConstraint("dedupe_key", name="uq_reminder_rules_dedupe_key"),
    )
    op.create_index(
        op.f("ix_reminder_rules_next_trigger_at"),
        "reminder_rules",
        ["next_trigger_at"],
    )
    op.create_index("ix_reminder_rules_due", "reminder_rules", ["is_active", "next_trigger_at"])
    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("reminder_rule_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("issue_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_employee_no", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("send_status", sa.String(), nullable=False),
        sa.Column("wecom_message_id", sa.String(), nullable=True),
        sa.Column("fail_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("retry_next_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "send_status IN ('pending', 'sent', 'failed', 'cancelled')",
            name="ck_notifications_send_status",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_notifications_retry_count"),
        sa.ForeignKeyConstraint(
            ["reminder_rule_id"],
            ["reminder_rules.reminder_rule_id"],
            name=op.f("fk_notifications_reminder_rule_id_reminder_rules"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_notifications_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["task_issues.issue_id"],
            name=op.f("fk_notifications_issue_id_task_issues"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_notifications_recipient_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("notification_id", name=op.f("pk_notifications")),
        sa.UniqueConstraint(
            "dedupe_key",
            "channel",
            "recipient_employee_no",
            name="uq_notifications_dedupe_recipient_channel",
        ),
    )
    op.create_index(
        "ix_notifications_recipient_status",
        "notifications",
        ["recipient_employee_no", "send_status", "created_at"],
    )
    op.create_table(
        "task_archives",
        sa.Column("archive_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("archive_snapshot", JSONB, nullable=False),
        sa.Column("source_status_snapshot", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("search_keywords", JSONB, nullable=False),
        sa.Column("review_result", sa.String(), nullable=True),
        sa.Column("risk_points", JSONB, nullable=False),
        sa.Column("reusable_template", JSONB, nullable=True),
        sa.Column("actual_hours_total", sa.Numeric(), nullable=True),
        sa.Column("archived_by_employee_no", sa.String(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_task_archives_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["archived_by_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_archives_archived_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("archive_id", name=op.f("pk_task_archives")),
        sa.UniqueConstraint("task_id", name="uq_task_archives_task"),
    )
    op.create_index(
        "ix_task_archives_keywords",
        "task_archives",
        ["search_keywords"],
        postgresql_using="gin",
    )
    op.create_table(
        "operation_logs",
        sa.Column("operation_log_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("operator_employee_no", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("object_type", sa.String(), nullable=False),
        sa.Column("object_id", sa.String(), nullable=False),
        sa.Column("before_data", JSONB, nullable=True),
        sa.Column("after_data", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["operator_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_operation_logs_operator_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("operation_log_id", name=op.f("pk_operation_logs")),
    )
    op.create_index("ix_operation_logs_request", "operation_logs", ["request_id"])
    op.create_index(
        "ix_operation_logs_object", "operation_logs", ["object_type", "object_id", "created_at"]
    )
    op.create_index(
        "ix_operation_logs_operator", "operation_logs", ["operator_employee_no", "created_at"]
    )
    op.create_table(
        "user_authorized_scopes",
        sa.Column("authorized_scope_id", sa.Uuid(), nullable=False),
        sa.Column("employee_no", sa.String(), nullable=False),
        sa.Column("scope_type", sa.String(), nullable=False),
        sa.Column("scope_id", sa.String(), nullable=True),
        sa.Column("permission_type", sa.String(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by_employee_no", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_user_authorized_scopes_validity",
        ),
        sa.CheckConstraint(
            "scope_type IN ('department', 'user', 'role', 'all_demo_data')",
            name="ck_user_authorized_scopes_scope_type",
        ),
        sa.CheckConstraint(
            "permission_type IN ('view', 'manage', 'export')",
            name="ck_user_authorized_scopes_permission_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'disabled')",
            name="ck_user_authorized_scopes_status",
        ),
        sa.ForeignKeyConstraint(
            ["employee_no"],
            ["users.employee_no"],
            name=op.f("fk_user_authorized_scopes_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_user_authorized_scopes_created_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("authorized_scope_id", name=op.f("pk_user_authorized_scopes")),
    )
    op.create_index(
        "ix_user_authorized_scopes_active",
        "user_authorized_scopes",
        ["employee_no", "status", "scope_type"],
    )
    op.create_table(
        "system_parameters",
        sa.Column("parameter_id", sa.Uuid(), nullable=False),
        sa.Column("param_key", sa.String(), nullable=False),
        sa.Column("param_name", sa.String(), nullable=False),
        sa.Column("param_value", sa.Text(), nullable=False),
        sa.Column("param_type", sa.String(), nullable=False),
        sa.Column("module", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("updated_by_employee_no", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "param_type IN ('number', 'string', 'boolean', 'json')",
            name="ck_system_parameters_type",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_system_parameters_updated_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("parameter_id", name=op.f("pk_system_parameters")),
        sa.UniqueConstraint("param_key", name="uq_system_parameters_key"),
    )
    op.create_index(
        "ix_system_parameters_module_active", "system_parameters", ["module", "is_active"]
    )
    op.bulk_insert(
        sa.table(
            "system_parameters",
            sa.column("parameter_id", sa.Uuid()),
            sa.column("param_key", sa.String()),
            sa.column("param_name", sa.String()),
            sa.column("param_value", sa.Text()),
            sa.column("param_type", sa.String()),
            sa.column("module", sa.String()),
            sa.column("description", sa.Text()),
            sa.column("is_active", sa.Boolean()),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "parameter_id": uuid,
                "param_key": key,
                "param_name": name,
                "param_value": value,
                "param_type": "number",
                "module": module,
                "description": description,
                "is_active": True,
                "updated_at": seeded_at,
            }
            for uuid, key, name, value, module, description in [
                (
                    "00000000-0000-0000-0000-000000000001",
                    "daily_capacity_hours",
                    "Daily capacity hours",
                    "8",
                    "workload",
                    "Default daily available hours",
                ),
                (
                    "00000000-0000-0000-0000-000000000002",
                    "standard_task_count",
                    "Standard task count",
                    "5",
                    "workload",
                    "Standard active task count",
                ),
                (
                    "00000000-0000-0000-0000-000000000003",
                    "standard_task_weight",
                    "Standard task weight",
                    "3",
                    "workload",
                    "Standard task weight",
                ),
                (
                    "00000000-0000-0000-0000-000000000004",
                    "emergency_tolerance_count",
                    "Emergency tolerance count",
                    "3",
                    "workload",
                    "Emergency task tolerance",
                ),
                (
                    "00000000-0000-0000-0000-000000000005",
                    "importance_threshold",
                    "Importance threshold",
                    "70",
                    "priority",
                    "Priority quadrant importance threshold",
                ),
                (
                    "00000000-0000-0000-0000-000000000006",
                    "urgency_threshold",
                    "Urgency threshold",
                    "70",
                    "priority",
                    "Priority quadrant urgency threshold",
                ),
            ]
        ],
    )


def downgrade() -> None:
    for index_name, table_name in [
        ("ix_system_parameters_module_active", "system_parameters"),
        ("ix_user_authorized_scopes_active", "user_authorized_scopes"),
        ("ix_operation_logs_operator", "operation_logs"),
        ("ix_operation_logs_object", "operation_logs"),
        ("ix_operation_logs_request", "operation_logs"),
        ("ix_task_archives_keywords", "task_archives"),
        ("ix_notifications_recipient_status", "notifications"),
        ("ix_reminder_rules_due", "reminder_rules"),
        ("ix_reminder_rules_next_trigger_at", "reminder_rules"),
        ("ix_task_conflicts_employee_status", "task_conflicts"),
        ("ix_task_priority_scores_task_calculated", "task_priority_scores"),
        ("ix_workload_snapshots_employee_period", "workload_snapshots"),
        ("ix_task_performance_matches_task_confirmation", "task_performance_matches"),
        ("ix_performance_metrics_name", "performance_metrics"),
        ("ix_performance_metrics_scope_status", "performance_metrics"),
    ]:
        op.drop_index(index_name, table_name=table_name)
    for table_name in [
        "system_parameters",
        "user_authorized_scopes",
        "operation_logs",
        "task_archives",
        "notifications",
        "reminder_rules",
        "task_conflicts",
        "task_priority_scores",
        "workload_snapshots",
        "task_performance_matches",
        "performance_metrics",
        "employee_profiles",
    ]:
        op.drop_table(table_name)
