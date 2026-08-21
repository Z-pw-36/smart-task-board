"""add immutable task change requests

Revision ID: d4a8e53b7c19
Revises: c31f8e7a4d02
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4a8e53b7c19"
down_revision: str | Sequence[str] | None = "c31f8e7a4d02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_change_requests",
        sa.Column("change_request_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("requester_employee_no", sa.String(), nullable=False),
        sa.Column("patch_json", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("before_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("after_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requester_task_version", sa.Integer(), nullable=False),
        sa.Column("base_task_version", sa.Integer(), nullable=False),
        sa.Column("decision_by_employee_no", sa.String(), nullable=True),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_comment", sa.String(), nullable=True),
        sa.Column("cancelled_by_employee_no", sa.String(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "btrim(reason) <> ''",
            name=op.f("ck_task_change_requests_reason_non_blank"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(patch_json) = 'object' AND patch_json <> '{}'::jsonb",
            name=op.f("ck_task_change_requests_patch_object_non_empty"),
        ),
        sa.CheckConstraint(
            "requester_task_version >= 1",
            name=op.f(
                "ck_task_change_requests_requester_task_version_positive"
            ),
        ),
        sa.CheckConstraint(
            "base_task_version >= 1",
            name=op.f("ck_task_change_requests_base_task_version_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name=op.f("ck_task_change_requests_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'pending' "
            "AND decision_by_employee_no IS NULL "
            "AND decision_at IS NULL "
            "AND decision_comment IS NULL "
            "AND cancelled_by_employee_no IS NULL "
            "AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) "
            "OR (status = 'approved' "
            "AND decision_by_employee_no IS NOT NULL "
            "AND decision_at IS NOT NULL "
            "AND cancelled_by_employee_no IS NULL "
            "AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) "
            "OR (status = 'rejected' "
            "AND decision_by_employee_no IS NOT NULL "
            "AND decision_at IS NOT NULL "
            "AND decision_comment IS NOT NULL "
            "AND btrim(decision_comment) <> '' "
            "AND cancelled_by_employee_no IS NULL "
            "AND cancelled_at IS NULL "
            "AND cancellation_reason IS NULL) "
            "OR (status = 'cancelled' "
            "AND cancelled_by_employee_no IS NOT NULL "
            "AND cancelled_at IS NOT NULL "
            "AND cancellation_reason IS NOT NULL "
            "AND btrim(cancellation_reason) <> '' "
            "AND decision_by_employee_no IS NULL "
            "AND decision_at IS NULL "
            "AND decision_comment IS NULL)",
            name=op.f("ck_task_change_requests_lifecycle_fields"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_task_change_requests_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requester_employee_no"],
            ["users.employee_no"],
            name=op.f("fk_task_change_requests_requester_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decision_by_employee_no"],
            ["users.employee_no"],
            name=op.f(
                "fk_task_change_requests_decision_by_employee_no_users"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_employee_no"],
            ["users.employee_no"],
            name=op.f(
                "fk_task_change_requests_cancelled_by_employee_no_users"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "change_request_id",
            name=op.f("pk_task_change_requests"),
        ),
    )
    op.create_index(
        "ix_task_change_requests_task_timeline",
        "task_change_requests",
        ["task_id", "created_at", "change_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_change_requests_task_status_timeline",
        "task_change_requests",
        ["task_id", "status", "created_at", "change_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_change_requests_requester_timeline",
        "task_change_requests",
        ["requester_employee_no", "created_at", "change_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_change_requests_status_timeline",
        "task_change_requests",
        ["status", "created_at", "change_request_id"],
        unique=False,
    )
    op.create_index(
        "uq_task_change_requests_one_pending_per_task",
        "task_change_requests",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_task_change_requests_one_pending_per_task",
        table_name="task_change_requests",
    )
    op.drop_index(
        "ix_task_change_requests_status_timeline",
        table_name="task_change_requests",
    )
    op.drop_index(
        "ix_task_change_requests_requester_timeline",
        table_name="task_change_requests",
    )
    op.drop_index(
        "ix_task_change_requests_task_status_timeline",
        table_name="task_change_requests",
    )
    op.drop_index(
        "ix_task_change_requests_task_timeline",
        table_name="task_change_requests",
    )
    op.drop_table("task_change_requests")

