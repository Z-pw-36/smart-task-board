from __future__ import annotations

from datetime import timedelta

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.models import (
    EmployeeProfile,
    Notification,
    OperationLog,
    PerformanceMetric,
    RefreshToken,
    ReminderRule,
    SystemParameter,
    TaskArchive,
    TaskConflict,
    TaskPerformanceMatch,
    TaskPriorityScore,
    UserAuthorizedScope,
    WorkloadSnapshot,
)

EXPECTED_COLUMNS: dict[type[object], set[str]] = {
    EmployeeProfile: {
        "employee_no",
        "responsibility_text",
        "skill_tags",
        "daily_capacity_hours",
        "standard_task_count",
        "standard_task_weight",
        "emergency_tolerance_count",
        "availability_status",
        "updated_at",
    },
    PerformanceMetric: {
        "metric_id",
        "metric_type",
        "period",
        "business_unit",
        "sequence_no",
        "dimension",
        "metric_name",
        "definition_formula",
        "weight",
        "target_value",
        "deliverable",
        "data_source",
        "status",
        "created_at",
        "updated_at",
    },
    TaskPerformanceMatch: {
        "performance_match_id",
        "task_id",
        "metric_id",
        "type_score",
        "business_unit_score",
        "metric_name_score",
        "definition_formula_score",
        "deliverable_score",
        "total_score",
        "match_level",
        "match_reason",
        "is_confirmed",
        "confirmed_by_employee_no",
        "confirmed_at",
        "algorithm_version",
        "created_at",
        "updated_at",
    },
    WorkloadSnapshot: {
        "workload_snapshot_id",
        "employee_no",
        "period_start",
        "period_end",
        "remaining_hours_sum",
        "available_hours",
        "active_task_count",
        "active_task_weight_sum",
        "urgent_task_count",
        "blocked_task_count",
        "overdue_task_count",
        "hours_pressure",
        "weight_pressure",
        "count_pressure",
        "urgent_pressure",
        "blocked_overdue_pressure",
        "workload_score",
        "workload_level",
        "parameter_snapshot",
        "calculated_at",
    },
    TaskPriorityScore: {
        "priority_score_id",
        "task_id",
        "task_weight_score",
        "performance_match_score",
        "report_to_level_score",
        "importance_score",
        "time_pressure_score",
        "overdue_pressure_score",
        "urgent_pressure_score",
        "urgency_score",
        "priority_quadrant",
        "remaining_hours",
        "sort_rank",
        "task_created_at_snapshot",
        "explanation",
        "calculated_at",
    },
    TaskConflict: {
        "conflict_id",
        "conflict_type",
        "employee_no",
        "task_id",
        "related_task_id",
        "node_id",
        "dedupe_key",
        "severity",
        "description",
        "suggestion",
        "status",
        "resolved_by_employee_no",
        "resolution_note",
        "detected_at",
        "resolved_at",
    },
    ReminderRule: {
        "reminder_rule_id",
        "task_id",
        "node_id",
        "issue_id",
        "reminder_type",
        "recipient_employee_no",
        "trigger_time",
        "next_trigger_at",
        "repeat_rule",
        "dedupe_key",
        "is_active",
        "last_triggered_at",
        "created_at",
    },
    Notification: {
        "notification_id",
        "reminder_rule_id",
        "task_id",
        "issue_id",
        "recipient_employee_no",
        "channel",
        "title",
        "content",
        "send_status",
        "wecom_message_id",
        "fail_reason",
        "retry_count",
        "retry_next_at",
        "sent_at",
        "read_at",
        "dedupe_key",
        "created_at",
    },
    TaskArchive: {
        "archive_id",
        "task_id",
        "archive_snapshot",
        "source_status_snapshot",
        "summary",
        "search_keywords",
        "review_result",
        "risk_points",
        "reusable_template",
        "actual_hours_total",
        "archived_by_employee_no",
        "archived_at",
    },
    OperationLog: {
        "operation_log_id",
        "request_id",
        "operator_employee_no",
        "action",
        "object_type",
        "object_id",
        "before_data",
        "after_data",
        "ip_address",
        "user_agent",
        "result",
        "error_message",
        "created_at",
    },
    UserAuthorizedScope: {
        "authorized_scope_id",
        "employee_no",
        "scope_type",
        "scope_id",
        "permission_type",
        "valid_from",
        "valid_to",
        "status",
        "created_by_employee_no",
        "created_at",
    },
    SystemParameter: {
        "parameter_id",
        "param_key",
        "param_name",
        "param_value",
        "param_type",
        "module",
        "description",
        "is_active",
        "updated_by_employee_no",
        "updated_at",
    },
    RefreshToken: {
        "refresh_token_id",
        "employee_no",
        "token_hash",
        "family_id",
        "status",
        "issued_at",
        "expires_at",
        "rotated_at",
        "revoked_at",
        "replaced_by_token_id",
        "client_id",
        "user_agent",
    },
}


def test_business_extension_columns_primary_keys_and_no_implicit_ids() -> None:
    for model, expected_columns in EXPECTED_COLUMNS.items():
        table = model.__table__
        assert set(table.columns.keys()) == expected_columns
        assert "id" not in table.columns
        assert len(table.primary_key.columns) == 1
        primary_column = next(iter(table.primary_key.columns))
        if model is EmployeeProfile:
            assert primary_column.name == "employee_no"
            assert isinstance(primary_column.type, String)
        else:
            assert primary_column.name.endswith("_id")
            assert isinstance(primary_column.type, Uuid)
            assert primary_column.default is not None
            assert primary_column.default.is_callable


def test_business_extension_json_numeric_boolean_and_time_columns() -> None:
    json_columns = {
        EmployeeProfile: {"skill_tags"},
        WorkloadSnapshot: {"parameter_snapshot"},
        TaskPriorityScore: {"explanation"},
        TaskArchive: {"archive_snapshot", "search_keywords", "risk_points", "reusable_template"},
        OperationLog: {"before_data", "after_data"},
    }
    numeric_columns = {
        "daily_capacity_hours",
        "weight",
        "type_score",
        "business_unit_score",
        "metric_name_score",
        "definition_formula_score",
        "deliverable_score",
        "total_score",
        "remaining_hours_sum",
        "available_hours",
        "active_task_weight_sum",
        "hours_pressure",
        "weight_pressure",
        "count_pressure",
        "urgent_pressure",
        "blocked_overdue_pressure",
        "workload_score",
        "task_weight_score",
        "performance_match_score",
        "report_to_level_score",
        "importance_score",
        "time_pressure_score",
        "overdue_pressure_score",
        "urgent_pressure_score",
        "urgency_score",
        "remaining_hours",
        "actual_hours_total",
    }

    for model, columns in json_columns.items():
        for column_name in columns:
            assert isinstance(model.__table__.c[column_name].type, JSONB)

    for model in EXPECTED_COLUMNS:
        for column_name in set(model.__table__.columns.keys()) & numeric_columns:
            assert isinstance(model.__table__.c[column_name].type, Numeric)
        for column in model.__table__.columns:
            if isinstance(column.type, DateTime):
                assert column.type.timezone is True
                if column.default is not None and column.default.is_callable:
                    value = column.default.arg(None)
                    assert value.tzinfo is not None
                    assert value.utcoffset() == timedelta(0)

    assert isinstance(TaskPerformanceMatch.__table__.c.is_confirmed.type, Boolean)
    assert isinstance(ReminderRule.__table__.c.is_active.type, Boolean)
    assert isinstance(SystemParameter.__table__.c.is_active.type, Boolean)


def test_business_extension_foreign_keys_and_lifecycle_checks() -> None:
    expected_fk_targets = {
        EmployeeProfile: {("employee_no",): ("users.employee_no",)},
        TaskPerformanceMatch: {
            ("task_id",): ("tasks.task_id",),
            ("metric_id",): ("performance_metrics.metric_id",),
            ("confirmed_by_employee_no",): ("users.employee_no",),
        },
        WorkloadSnapshot: {("employee_no",): ("users.employee_no",)},
        TaskPriorityScore: {("task_id",): ("tasks.task_id",)},
        TaskConflict: {
            ("employee_no",): ("users.employee_no",),
            ("task_id",): ("tasks.task_id",),
            ("related_task_id",): ("tasks.task_id",),
            ("node_id",): ("task_nodes.node_id",),
            ("resolved_by_employee_no",): ("users.employee_no",),
        },
        ReminderRule: {
            ("task_id",): ("tasks.task_id",),
            ("node_id",): ("task_nodes.node_id",),
            ("issue_id",): ("task_issues.issue_id",),
            ("recipient_employee_no",): ("users.employee_no",),
        },
        Notification: {
            ("reminder_rule_id",): ("reminder_rules.reminder_rule_id",),
            ("task_id",): ("tasks.task_id",),
            ("issue_id",): ("task_issues.issue_id",),
            ("recipient_employee_no",): ("users.employee_no",),
        },
        TaskArchive: {
            ("task_id",): ("tasks.task_id",),
            ("archived_by_employee_no",): ("users.employee_no",),
        },
        OperationLog: {("operator_employee_no",): ("users.employee_no",)},
        UserAuthorizedScope: {
            ("employee_no",): ("users.employee_no",),
            ("created_by_employee_no",): ("users.employee_no",),
        },
        SystemParameter: {("updated_by_employee_no",): ("users.employee_no",)},
        RefreshToken: {
            ("employee_no",): ("users.employee_no",),
            ("replaced_by_token_id",): ("auth_refresh_tokens.refresh_token_id",),
        },
    }

    for model, expected in expected_fk_targets.items():
        table = model.__table__
        actual = {
            (
                tuple(column.name for column in constraint.columns),
                tuple(element.target_fullname for element in constraint.elements),
                constraint.ondelete,
            )
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }
        assert actual == {(columns, targets, "RESTRICT") for columns, targets in expected.items()}

    for model in EXPECTED_COLUMNS:
        check_names = {
            constraint.name
            for constraint in model.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        }
        if model in {
            PerformanceMetric,
            TaskPerformanceMatch,
            TaskConflict,
            ReminderRule,
            Notification,
        }:
            assert check_names


def test_business_extension_dedupe_indexes_and_unique_constraints() -> None:
    expected_index_columns = {
        PerformanceMetric: {
            ("ix_performance_metrics_scope_status", ("business_unit", "status"), False),
            ("ix_performance_metrics_name", ("metric_name",), False),
        },
        TaskPerformanceMatch: {
            (
                "ix_task_performance_matches_task_confirmation",
                ("task_id", "is_confirmed", "total_score"),
                False,
            ),
        },
        WorkloadSnapshot: {
            (
                "ix_workload_snapshots_employee_period",
                ("employee_no", "period_start", "period_end"),
                False,
            ),
        },
        TaskPriorityScore: {
            ("ix_task_priority_scores_task_calculated", ("task_id", "calculated_at"), False),
        },
        TaskConflict: {
            ("ix_task_conflicts_employee_status", ("employee_no", "status", "severity"), False),
        },
        ReminderRule: {
            ("ix_reminder_rules_next_trigger_at", ("next_trigger_at",), False),
            ("ix_reminder_rules_due", ("is_active", "next_trigger_at"), False),
        },
        Notification: {
            (
                "ix_notifications_recipient_status",
                ("recipient_employee_no", "send_status", "created_at"),
                False,
            ),
        },
        TaskArchive: {
            ("ix_task_archives_keywords", ("search_keywords",), False),
        },
        OperationLog: {
            ("ix_operation_logs_request", ("request_id",), False),
            ("ix_operation_logs_object", ("object_type", "object_id", "created_at"), False),
            ("ix_operation_logs_operator", ("operator_employee_no", "created_at"), False),
        },
        UserAuthorizedScope: {
            ("ix_user_authorized_scopes_active", ("employee_no", "status", "scope_type"), False),
        },
        SystemParameter: {
            ("ix_system_parameters_module_active", ("module", "is_active"), False),
        },
        RefreshToken: {
            (
                "ix_auth_refresh_tokens_employee_status",
                ("employee_no", "status", "expires_at"),
                False,
            ),
        },
    }

    for model, expected in expected_index_columns.items():
        actual = {
            (str(index.name), tuple(column.name for column in index.columns), bool(index.unique))
            for index in model.__table__.indexes
        }
        assert actual == expected

    assert "uq_task_conflicts_dedupe_key" in {
        constraint.name for constraint in TaskConflict.__table__.constraints
    }
    assert "uq_reminder_rules_dedupe_key" in {
        constraint.name for constraint in ReminderRule.__table__.constraints
    }
    assert "uq_notifications_dedupe_recipient_channel" in {
        constraint.name for constraint in Notification.__table__.constraints
    }
    assert "uq_task_archives_task" in {
        constraint.name for constraint in TaskArchive.__table__.constraints
    }
    assert "uq_auth_refresh_tokens_hash" in {
        constraint.name for constraint in RefreshToken.__table__.constraints
    }
