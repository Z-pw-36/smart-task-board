"""add progress reports and task issues

Revision ID: 576787492bd1
Revises: 17f69ea12754
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "576787492bd1"
down_revision: str | Sequence[str] | None = "17f69ea12754"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REPORT_CYCLE_PATTERN = (
    "^weekly:(MON|TUE|WED|THU|FRI|SAT|SUN)@"
    "([01][0-9]|2[0-3]):[0-5][0-9]$"
)


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            DO $batch2a$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM tasks
                    WHERE report_cycle IS NOT NULL
                      AND report_cycle !~ '{REPORT_CYCLE_PATTERN}'
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'tasks.report_cycle contains values outside the approved format';
                END IF;
            END
            $batch2a$;
            """
        )
    )
    op.create_check_constraint(
        "ck_tasks_report_cycle_format",
        "tasks",
        "report_cycle IS NULL OR report_cycle ~ "
        f"'{REPORT_CYCLE_PATTERN}'",
    )
    op.create_table(
        "task_progress_reports",
        sa.Column("progress_report_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("reporter_employee_no", sa.String(), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("report_content", sa.String(), nullable=False),
        sa.Column("stage_result", sa.String(), nullable=True),
        sa.Column("difficulty", sa.String(), nullable=True),
        sa.Column("resource_request", sa.String(), nullable=True),
        sa.Column("actual_hours", sa.Numeric(), nullable=True),
        sa.Column("corrects_report_id", sa.Uuid(), nullable=True),
        sa.Column("report_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_version", sa.Integer(), nullable=False),
        sa.Column("operation_source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actual_hours IS NULL OR actual_hours >= 0",
            name=op.f("ck_task_progress_reports_actual_hours_non_negative"),
        ),
        sa.CheckConstraint(
            "btrim(report_content) <> ''",
            name=op.f("ck_task_progress_reports_content_non_blank"),
        ),
        sa.CheckConstraint(
            "node_id IS NULL "
            "OR (report_period_start IS NULL AND report_period_end IS NULL)",
            name=op.f("ck_task_progress_reports_node_period_absent"),
        ),
        sa.CheckConstraint(
            "corrects_report_id IS NULL "
            "OR corrects_report_id <> progress_report_id",
            name=op.f("ck_task_progress_reports_not_self_correction"),
        ),
        sa.CheckConstraint(
            "btrim(operation_source) <> ''",
            name=op.f("ck_task_progress_reports_operation_source_non_blank"),
        ),
        sa.CheckConstraint(
            "report_period_start IS NULL "
            "OR report_period_end > report_period_start",
            name=op.f("ck_task_progress_reports_period_order"),
        ),
        sa.CheckConstraint(
            "(report_period_start IS NULL AND report_period_end IS NULL) "
            "OR (report_period_start IS NOT NULL AND report_period_end IS NOT NULL)",
            name=op.f("ck_task_progress_reports_period_pair"),
        ),
        sa.CheckConstraint(
            "progress_percent BETWEEN 0 AND 100",
            name=op.f("ck_task_progress_reports_progress_percent_range"),
        ),
        sa.CheckConstraint(
            "task_version >= 1",
            name=op.f("ck_task_progress_reports_task_version_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "corrects_report_id"],
            [
                "task_progress_reports.task_id",
                "task_progress_reports.progress_report_id",
            ],
            name="fk_task_progress_reports_corrected_report_same_task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "node_id"],
            ["task_nodes.task_id", "task_nodes.node_id"],
            name="fk_task_progress_reports_node_same_task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reporter_employee_no"],
            ["users.employee_no"],
            name=op.f(
                "fk_task_progress_reports_reporter_employee_no_users"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_task_progress_reports_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "progress_report_id",
            name=op.f("pk_task_progress_reports"),
        ),
        sa.UniqueConstraint(
            "task_id",
            "progress_report_id",
            name="uq_task_progress_reports_task_report",
        ),
    )
    op.create_index(
        "ix_task_progress_reports_corrects_report_id",
        "task_progress_reports",
        ["corrects_report_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_progress_reports_node_timeline",
        "task_progress_reports",
        ["task_id", "node_id", "created_at", "progress_report_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_progress_reports_reporter_timeline",
        "task_progress_reports",
        ["reporter_employee_no", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_progress_reports_task_timeline",
        "task_progress_reports",
        ["task_id", "created_at", "progress_report_id"],
        unique=False,
    )
    op.create_index(
        "uq_task_progress_reports_one_current_task_period",
        "task_progress_reports",
        ["task_id", "report_period_end"],
        unique=True,
        postgresql_where=sa.text(
            "node_id IS NULL "
            "AND corrects_report_id IS NULL "
            "AND report_period_end IS NOT NULL"
        ),
    )
    op.create_table(
        "task_issues",
        sa.Column("issue_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("source_progress_report_id", sa.Uuid(), nullable=True),
        sa.Column("reported_by_employee_no", sa.String(), nullable=False),
        sa.Column("issue_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("requested_resource", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("owner_employee_no", sa.String(), nullable=False),
        sa.Column("resolution_note", sa.String(), nullable=True),
        sa.Column("resolved_by_employee_no", sa.String(), nullable=True),
        sa.Column("rejected_by_employee_no", sa.String(), nullable=True),
        sa.Column("closed_by_employee_no", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status NOT IN ('open', 'processing') "
            "OR (resolved_at IS NULL "
            "AND rejected_at IS NULL "
            "AND closed_at IS NULL "
            "AND resolved_by_employee_no IS NULL "
            "AND rejected_by_employee_no IS NULL "
            "AND closed_by_employee_no IS NULL "
            "AND resolution_note IS NULL)",
            name=op.f("ck_task_issues_active_lifecycle_fields_absent"),
        ),
        sa.CheckConstraint(
            "status <> 'closed' "
            "OR (closed_at IS NOT NULL "
            "AND closed_by_employee_no IS NOT NULL "
            "AND resolution_note IS NOT NULL "
            "AND btrim(resolution_note) <> '' "
            "AND ((resolved_at IS NOT NULL "
            "AND resolved_by_employee_no IS NOT NULL "
            "AND rejected_at IS NULL "
            "AND rejected_by_employee_no IS NULL) "
            "OR (rejected_at IS NOT NULL "
            "AND rejected_by_employee_no IS NOT NULL "
            "AND resolved_at IS NULL "
            "AND resolved_by_employee_no IS NULL)))",
            name=op.f("ck_task_issues_closed_fields"),
        ),
        sa.CheckConstraint(
            "btrim(description) <> ''",
            name=op.f("ck_task_issues_description_non_blank"),
        ),
        sa.CheckConstraint(
            "issue_type IN "
            "('blocker', 'resource_request', 'collaboration_support', 'risk')",
            name=op.f("ck_task_issues_issue_type_allowed"),
        ),
        sa.CheckConstraint(
            "status <> 'open' OR processing_started_at IS NULL",
            name=op.f("ck_task_issues_open_not_processing"),
        ),
        sa.CheckConstraint(
            "status <> 'processing' OR processing_started_at IS NOT NULL",
            name=op.f("ck_task_issues_processing_started"),
        ),
        sa.CheckConstraint(
            "status <> 'rejected' "
            "OR (resolved_at IS NULL "
            "AND resolved_by_employee_no IS NULL "
            "AND closed_at IS NULL "
            "AND closed_by_employee_no IS NULL)",
            name=op.f("ck_task_issues_rejected_exclusive"),
        ),
        sa.CheckConstraint(
            "status <> 'rejected' "
            "OR (rejected_at IS NOT NULL "
            "AND rejected_by_employee_no IS NOT NULL "
            "AND resolution_note IS NOT NULL "
            "AND btrim(resolution_note) <> '')",
            name=op.f("ck_task_issues_rejected_fields"),
        ),
        sa.CheckConstraint(
            "issue_type <> 'resource_request' "
            "OR (requested_resource IS NOT NULL "
            "AND btrim(requested_resource) <> '')",
            name=op.f("ck_task_issues_resource_request_requires_resource"),
        ),
        sa.CheckConstraint(
            "status <> 'resolved' "
            "OR (rejected_at IS NULL "
            "AND rejected_by_employee_no IS NULL "
            "AND closed_at IS NULL "
            "AND closed_by_employee_no IS NULL)",
            name=op.f("ck_task_issues_resolved_exclusive"),
        ),
        sa.CheckConstraint(
            "status <> 'resolved' "
            "OR (resolved_at IS NOT NULL "
            "AND resolved_by_employee_no IS NOT NULL "
            "AND resolution_note IS NOT NULL "
            "AND btrim(resolution_note) <> '')",
            name=op.f("ck_task_issues_resolved_fields"),
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name=op.f("ck_task_issues_severity_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'processing', 'resolved', 'rejected', 'closed')",
            name=op.f("ck_task_issues_status_allowed"),
        ),
        sa.CheckConstraint(
            "btrim(title) <> ''",
            name=op.f("ck_task_issues_title_non_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["closed_by_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_issues_closed_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "node_id"],
            ["task_nodes.task_id", "task_nodes.node_id"],
            name="fk_task_issues_node_same_task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_issues_owner_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_issues_rejected_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reported_by_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_issues_reported_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_issues_resolved_by_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "source_progress_report_id"],
            [
                "task_progress_reports.task_id",
                "task_progress_reports.progress_report_id",
            ],
            name="fk_task_issues_source_report_same_task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_task_issues_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("issue_id", name=op.f("pk_task_issues")),
    )
    op.create_index(
        "ix_task_issues_active_task_node",
        "task_issues",
        ["task_id", "node_id"],
        unique=False,
        postgresql_where=sa.text("status IN ('open', 'processing')"),
    )
    op.create_index(
        "ix_task_issues_node_status",
        "task_issues",
        ["task_id", "node_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_task_issues_owner_status_timeline",
        "task_issues",
        ["owner_employee_no", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_issues_source_progress_report_id",
        "task_issues",
        ["source_progress_report_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_issues_task_status_timeline",
        "task_issues",
        ["task_id", "status", "created_at", "issue_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_issues_task_timeline",
        "task_issues",
        ["task_id", "created_at", "issue_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_issues_task_timeline", table_name="task_issues")
    op.drop_index(
        "ix_task_issues_task_status_timeline",
        table_name="task_issues",
    )
    op.drop_index(
        "ix_task_issues_source_progress_report_id",
        table_name="task_issues",
    )
    op.drop_index(
        "ix_task_issues_owner_status_timeline",
        table_name="task_issues",
    )
    op.drop_index("ix_task_issues_node_status", table_name="task_issues")
    op.drop_index(
        "ix_task_issues_active_task_node",
        table_name="task_issues",
        postgresql_where=sa.text("status IN ('open', 'processing')"),
    )
    op.drop_table("task_issues")
    op.drop_index(
        "uq_task_progress_reports_one_current_task_period",
        table_name="task_progress_reports",
        postgresql_where=sa.text(
            "node_id IS NULL "
            "AND corrects_report_id IS NULL "
            "AND report_period_end IS NOT NULL"
        ),
    )
    op.drop_index(
        "ix_task_progress_reports_task_timeline",
        table_name="task_progress_reports",
    )
    op.drop_index(
        "ix_task_progress_reports_reporter_timeline",
        table_name="task_progress_reports",
    )
    op.drop_index(
        "ix_task_progress_reports_node_timeline",
        table_name="task_progress_reports",
    )
    op.drop_index(
        "ix_task_progress_reports_corrects_report_id",
        table_name="task_progress_reports",
    )
    op.drop_table("task_progress_reports")
    op.drop_constraint(
        "ck_tasks_report_cycle_format",
        "tasks",
        type_="check",
    )
