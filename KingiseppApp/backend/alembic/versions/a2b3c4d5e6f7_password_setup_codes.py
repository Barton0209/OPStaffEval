"""add single-use password setup codes

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
"""

from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_setup_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_password_setup_codes_user_id", "password_setup_codes", ["user_id"])
    op.create_index("ix_password_setup_codes_expires_at", "password_setup_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_password_setup_codes_expires_at", table_name="password_setup_codes")
    op.drop_index("ix_password_setup_codes_user_id", table_name="password_setup_codes")
    op.drop_table("password_setup_codes")
