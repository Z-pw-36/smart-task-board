"""add task completion review rounds

Revision ID: c31f8e7a4d02
Revises: 576787492bd1
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c31f8e7a4d02"
down_revision: str | Sequence[str] | None = "576787492bd1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $completion_review_preflight$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM tasks AS task
                    WHERE task.status IN ('pending_review', 'completed')
                      AND NOT EXISTS (
                          SELECT 1
                          FROM task_status_logs AS submission
                          WHERE submission.task_id = task.task_id
                            AND submission.action_type = 'completion_submitted'
                      )
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'pending_review/completed task lacks completion submission history';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM task_status_logs
                    WHERE action_type = 'completion_submitted'
                      AND (
                          operator_employee_no IS NULL
                          OR target_employee_no IS NULL
                      )
                ) OR EXISTS (
                    SELECT 1
                    FROM task_status_logs
                    WHERE action_type = 'completion_approved'
                      AND operator_employee_no IS NULL
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'completion history contains a null required actor';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM task_status_logs AS approval
                    WHERE approval.action_type = 'completion_approved'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM task_status_logs AS submission
                          WHERE submission.task_id = approval.task_id
                            AND submission.action_type = 'completion_submitted'
                            AND submission.task_version < approval.task_version
                      )
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'completion approval lacks an earlier submission';
                END IF;

                IF EXISTS (
                    WITH ordered_submissions AS (
                        SELECT
                            submission.*,
                            lead(submission.task_version) OVER (
                                PARTITION BY submission.task_id
                                ORDER BY
                                    submission.task_version,
                                    submission.created_at,
                                    submission.status_log_id
                            ) AS next_submitted_task_version
                        FROM task_status_logs AS submission
                        WHERE submission.action_type = 'completion_submitted'
                    )
                    SELECT 1
                    FROM ordered_submissions AS submission
                    JOIN task_status_logs AS approval
                      ON approval.task_id = submission.task_id
                     AND approval.action_type = 'completion_approved'
                     AND approval.task_version > submission.task_version
                     AND (
                         submission.next_submitted_task_version IS NULL
                         OR approval.task_version
                            < submission.next_submitted_task_version
                     )
                    GROUP BY
                        submission.status_log_id,
                        submission.target_employee_no,
                        submission.task_version,
                        submission.created_at
                    HAVING count(*) > 1
                        OR bool_or(
                            approval.operator_employee_no
                                <> submission.target_employee_no
                            OR approval.task_version
                                <= submission.task_version
                            OR approval.created_at < submission.created_at
                        )
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'completion submission has inconsistent approval history';
                END IF;

                IF EXISTS (
                    WITH ordered_submissions AS (
                        SELECT
                            submission.*,
                            lead(submission.task_version) OVER (
                                PARTITION BY submission.task_id
                                ORDER BY
                                    submission.task_version,
                                    submission.created_at,
                                    submission.status_log_id
                            ) AS next_submitted_task_version
                        FROM task_status_logs AS submission
                        WHERE submission.action_type = 'completion_submitted'
                    ),
                    submission_decisions AS (
                        SELECT
                            submission.task_id,
                            submission.status_log_id,
                            approval.status_log_id AS approval_log_id
                        FROM ordered_submissions AS submission
                        LEFT JOIN LATERAL (
                            SELECT candidate.status_log_id
                            FROM task_status_logs AS candidate
                            WHERE candidate.task_id = submission.task_id
                              AND candidate.action_type = 'completion_approved'
                              AND candidate.task_version
                                  > submission.task_version
                              AND (
                                  submission.next_submitted_task_version IS NULL
                                  OR candidate.task_version
                                      < submission.next_submitted_task_version
                              )
                            ORDER BY
                                candidate.task_version,
                                candidate.created_at,
                                candidate.status_log_id
                            LIMIT 1
                        ) AS approval ON true
                    )
                    SELECT 1
                    FROM submission_decisions
                    GROUP BY task_id
                    HAVING count(*) FILTER (
                        WHERE approval_log_id IS NULL
                    ) > 1
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'task contains multiple unresolved completion submissions';
                END IF;

                IF EXISTS (
                    WITH ordered_submissions AS (
                        SELECT
                            submission.*,
                            lead(submission.task_version) OVER (
                                PARTITION BY submission.task_id
                                ORDER BY
                                    submission.task_version,
                                    submission.created_at,
                                    submission.status_log_id
                            ) AS next_submitted_task_version
                        FROM task_status_logs AS submission
                        WHERE submission.action_type = 'completion_submitted'
                    ),
                    unresolved_submissions AS (
                        SELECT
                            submission.task_id,
                            submission.status_log_id,
                            submission.next_submitted_task_version
                        FROM ordered_submissions AS submission
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM task_status_logs AS approval
                            WHERE approval.task_id = submission.task_id
                              AND approval.action_type = 'completion_approved'
                              AND approval.task_version
                                  > submission.task_version
                              AND (
                                  submission.next_submitted_task_version IS NULL
                                  OR approval.task_version
                                      < submission.next_submitted_task_version
                              )
                        )
                    )
                    SELECT 1
                    FROM unresolved_submissions AS submission
                    JOIN tasks AS task ON task.task_id = submission.task_id
                    WHERE task.status = 'completed'
                       OR submission.next_submitted_task_version IS NOT NULL
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'completion history contains a stale unresolved submission';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM tasks AS task
                    WHERE EXISTS (
                        SELECT 1
                        FROM task_status_logs AS submission
                        WHERE submission.task_id = task.task_id
                          AND submission.action_type = 'completion_submitted'
                    )
                      AND task.status NOT IN ('pending_review', 'completed')
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'completion history conflicts with current task status';
                END IF;

                IF EXISTS (
                    WITH latest_submissions AS (
                        SELECT DISTINCT ON (submission.task_id)
                            submission.task_id,
                            submission.task_version
                        FROM task_status_logs AS submission
                        WHERE submission.action_type = 'completion_submitted'
                        ORDER BY
                            submission.task_id,
                            submission.task_version DESC,
                            submission.created_at DESC,
                            submission.status_log_id DESC
                    )
                    SELECT 1
                    FROM tasks AS task
                    JOIN latest_submissions AS submission
                      ON submission.task_id = task.task_id
                    LEFT JOIN LATERAL (
                        SELECT approval.status_log_id
                        FROM task_status_logs AS approval
                        WHERE approval.task_id = task.task_id
                          AND approval.action_type = 'completion_approved'
                          AND approval.task_version > submission.task_version
                        ORDER BY
                            approval.task_version,
                            approval.created_at,
                            approval.status_log_id
                        LIMIT 1
                    ) AS approval ON true
                    WHERE (
                        task.status = 'pending_review'
                        AND approval.status_log_id IS NOT NULL
                    ) OR (
                        task.status = 'completed'
                        AND approval.status_log_id IS NULL
                    )
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'latest completion decision conflicts with task status';
                END IF;
            END
            $completion_review_preflight$;
            """
        )
    )

    op.create_table(
        "task_completion_reviews",
        sa.Column("completion_review_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("review_round", sa.Integer(), nullable=False),
        sa.Column("submitted_by_employee_no", sa.String(), nullable=False),
        sa.Column("completion_note", sa.String(), nullable=True),
        sa.Column("deliverable_summary", sa.String(), nullable=True),
        sa.Column("reviewer_employee_no", sa.String(), nullable=False),
        sa.Column("review_status", sa.String(), nullable=False),
        sa.Column("review_result", sa.String(), nullable=True),
        sa.Column("reject_reason", sa.String(), nullable=True),
        sa.Column("rework_node_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_task_version", sa.Integer(), nullable=False),
        sa.Column("reviewed_task_version", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_legacy_import", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "completion_note IS NULL OR btrim(completion_note) <> ''",
            name=op.f(
                "ck_task_completion_reviews_completion_note_non_blank"
            ),
        ),
        sa.CheckConstraint(
            "deliverable_summary IS NULL "
            "OR btrim(deliverable_summary) <> ''",
            name=op.f(
                "ck_task_completion_reviews_deliverable_summary_non_blank"
            ),
        ),
        sa.CheckConstraint(
            "(review_status = 'submitted' "
            "AND review_result IS NULL "
            "AND reject_reason IS NULL "
            "AND rework_node_id IS NULL "
            "AND reviewed_at IS NULL "
            "AND reviewed_task_version IS NULL) "
            "OR (review_status = 'approved' "
            "AND review_result = 'approved' "
            "AND reject_reason IS NULL "
            "AND rework_node_id IS NULL "
            "AND reviewed_at IS NOT NULL "
            "AND reviewed_at >= submitted_at "
            "AND reviewed_task_version IS NOT NULL "
            "AND reviewed_task_version > submitted_task_version) "
            "OR (review_status = 'rejected' "
            "AND review_result = 'rejected' "
            "AND reject_reason IS NOT NULL "
            "AND btrim(reject_reason) <> '' "
            "AND reviewed_at IS NOT NULL "
            "AND reviewed_at >= submitted_at "
            "AND reviewed_task_version IS NOT NULL "
            "AND reviewed_task_version > submitted_task_version)",
            name=op.f("ck_task_completion_reviews_lifecycle_fields"),
        ),
        sa.CheckConstraint(
            "is_legacy_import "
            "OR (completion_note IS NOT NULL "
            "AND deliverable_summary IS NOT NULL)",
            name=op.f(
                "ck_task_completion_reviews_nonlegacy_content_present"
            ),
        ),
        sa.CheckConstraint(
            "review_result IS NULL "
            "OR review_result IN ('approved', 'rejected')",
            name=op.f(
                "ck_task_completion_reviews_review_result_allowed"
            ),
        ),
        sa.CheckConstraint(
            "review_round >= 1",
            name=op.f(
                "ck_task_completion_reviews_review_round_positive"
            ),
        ),
        sa.CheckConstraint(
            "review_status IN ('submitted', 'approved', 'rejected')",
            name=op.f(
                "ck_task_completion_reviews_review_status_allowed"
            ),
        ),
        sa.CheckConstraint(
            "submitted_task_version >= 1",
            name=op.f(
                "ck_task_completion_reviews_submitted_version_positive"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_employee_no"],
            ["users.employee_no"],
            name=op.f(
                "fk_task_completion_reviews_reviewer_employee_no_users"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "rework_node_id"],
            ["task_nodes.task_id", "task_nodes.node_id"],
            name="fk_task_completion_reviews_rework_node_same_task",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_employee_no"],
            ["users.employee_no"],
            name=op.f(
                "fk_task_completion_reviews_submitted_by_employee_no_users"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_task_completion_reviews_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "completion_review_id",
            name=op.f("pk_task_completion_reviews"),
        ),
        sa.UniqueConstraint(
            "task_id",
            "review_round",
            name="uq_task_completion_reviews_task_round",
        ),
    )
    op.create_index(
        "ix_task_completion_reviews_reviewer_status_timeline",
        "task_completion_reviews",
        [
            "reviewer_employee_no",
            "review_status",
            "submitted_at",
            "completion_review_id",
        ],
        unique=False,
    )
    op.create_index(
        "ix_task_completion_reviews_rework_node",
        "task_completion_reviews",
        ["task_id", "rework_node_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_completion_reviews_submitter_timeline",
        "task_completion_reviews",
        [
            "submitted_by_employee_no",
            "submitted_at",
            "completion_review_id",
        ],
        unique=False,
    )
    op.create_index(
        "ix_task_completion_reviews_task_timeline",
        "task_completion_reviews",
        [
            "task_id",
            "review_round",
            "submitted_at",
            "completion_review_id",
        ],
        unique=False,
    )
    op.create_index(
        "uq_task_completion_reviews_one_submitted_per_task",
        "task_completion_reviews",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("review_status = 'submitted'"),
    )

    op.execute(
        sa.text(
            """
            WITH ordered_submissions AS (
                SELECT
                    submission.*,
                    row_number() OVER (
                        PARTITION BY submission.task_id
                        ORDER BY
                            submission.task_version,
                            submission.created_at,
                            submission.status_log_id
                    )::integer AS review_round,
                    lead(submission.task_version) OVER (
                        PARTITION BY submission.task_id
                        ORDER BY
                            submission.task_version,
                            submission.created_at,
                            submission.status_log_id
                    ) AS next_submitted_task_version
                FROM task_status_logs AS submission
                WHERE submission.action_type = 'completion_submitted'
            ),
            legacy_rounds AS (
                SELECT
                    submission.*,
                    approval.operator_employee_no
                        AS approval_operator_employee_no,
                    approval.task_version AS approval_task_version,
                    approval.created_at AS approval_created_at
                FROM ordered_submissions AS submission
                LEFT JOIN LATERAL (
                    SELECT candidate.*
                    FROM task_status_logs AS candidate
                    WHERE candidate.task_id = submission.task_id
                      AND candidate.action_type = 'completion_approved'
                      AND candidate.task_version > submission.task_version
                      AND (
                          submission.next_submitted_task_version IS NULL
                          OR candidate.task_version
                              < submission.next_submitted_task_version
                      )
                    ORDER BY
                        candidate.task_version,
                        candidate.created_at,
                        candidate.status_log_id
                    LIMIT 1
                ) AS approval ON true
            )
            INSERT INTO task_completion_reviews (
                completion_review_id,
                task_id,
                review_round,
                submitted_by_employee_no,
                completion_note,
                deliverable_summary,
                reviewer_employee_no,
                review_status,
                review_result,
                reject_reason,
                rework_node_id,
                submitted_task_version,
                reviewed_task_version,
                submitted_at,
                reviewed_at,
                is_legacy_import
            )
            SELECT
                submission.status_log_id,
                submission.task_id,
                submission.review_round,
                submission.operator_employee_no,
                NULL,
                NULL,
                submission.target_employee_no,
                CASE
                    WHEN submission.approval_task_version IS NULL
                        THEN 'submitted'
                    ELSE 'approved'
                END,
                CASE
                    WHEN submission.approval_task_version IS NULL THEN NULL
                    ELSE 'approved'
                END,
                NULL,
                NULL,
                submission.task_version,
                submission.approval_task_version,
                submission.created_at,
                submission.approval_created_at,
                true
            FROM legacy_rounds AS submission
            ORDER BY submission.task_id, submission.review_round;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $completion_review_downgrade_guard$
            BEGIN
                IF EXISTS (SELECT 1 FROM task_completion_reviews) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'cannot downgrade while completion review history exists';
                END IF;
            END
            $completion_review_downgrade_guard$;
            """
        )
    )
    op.drop_index(
        "uq_task_completion_reviews_one_submitted_per_task",
        table_name="task_completion_reviews",
        postgresql_where=sa.text("review_status = 'submitted'"),
    )
    op.drop_index(
        "ix_task_completion_reviews_task_timeline",
        table_name="task_completion_reviews",
    )
    op.drop_index(
        "ix_task_completion_reviews_submitter_timeline",
        table_name="task_completion_reviews",
    )
    op.drop_index(
        "ix_task_completion_reviews_rework_node",
        table_name="task_completion_reviews",
    )
    op.drop_index(
        "ix_task_completion_reviews_reviewer_status_timeline",
        table_name="task_completion_reviews",
    )
    op.drop_table("task_completion_reviews")
