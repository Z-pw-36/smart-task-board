"""Add hashed refresh-token rotation records.

Revision ID: f7b8c9d0e1f2
Revises: e6f1a2b3c4d5
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f7b8c9d0e1f2"
down_revision: str | None = "e6f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_refresh_tokens",
        sa.Column("refresh_token_id", sa.Uuid(), nullable=False),
        sa.Column("employee_no", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", sa.Uuid(), nullable=True),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'rotated', 'revoked', 'expired')",
            name="ck_auth_refresh_tokens_status",
        ),
        sa.ForeignKeyConstraint(
            ["employee_no"],
            ["users.employee_no"],
            name=op.f("fk_auth_refresh_tokens_employee_no_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_token_id"],
            ["auth_refresh_tokens.refresh_token_id"],
            name=op.f("fk_auth_refresh_tokens_replaced_by_token_id_auth_refresh_tokens"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("refresh_token_id", name=op.f("pk_auth_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_hash"),
    )
    op.create_index(
        "ix_auth_refresh_tokens_employee_status",
        "auth_refresh_tokens",
        ["employee_no", "status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_refresh_tokens_employee_status", table_name="auth_refresh_tokens")
    op.drop_table("auth_refresh_tokens")
