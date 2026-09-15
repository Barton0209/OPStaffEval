"""add_control_models_and_security_fixes

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-09-15

Новые модели для «Контроль» входа:
- territories, departments, groups_of_users, user_territory_mappings
- import_logs, fired_employees, transfers
- registry_imports, registry_scores

Дополнительно:
- must_change_password на users (если отсутствует)
- token_version на users (если отсутствует)
"""

from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Territories ---
    op.create_table(
        "territories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("code", sa.String(128), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- Departments ---
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("code", sa.String(64), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("system_role", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- Groups of Users ---
    op.create_table(
        "groups_of_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("territory_id", sa.Integer(), sa.ForeignKey("territories.id"), nullable=True),
        sa.Column("territory_name", sa.String(255), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("department_name", sa.String(128), nullable=True),
        sa.Column("group_name", sa.String(128), nullable=True),
        sa.Column("permission", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- User Territory Mappings ---
    op.create_table(
        "user_territory_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("territory_id", sa.Integer(), sa.ForeignKey("territories.id"), nullable=True),
        sa.Column("territory_name", sa.String(255), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("department_name", sa.String(128), nullable=True),
        sa.Column("group_name", sa.String(128), nullable=True),
        sa.Column("actual_position", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- Import Logs ---
    op.create_table(
        "import_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("block_name", sa.String(128), nullable=False),
        sa.Column("slot_name", sa.String(128), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("added", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("skipped", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("archived", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("errors_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_preview", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default=sa.text("1"), nullable=False),
    )

    # --- Fired Employees ---
    op.create_table(
        "fired_employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("original_employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("tab_no", sa.String(64), nullable=False, index=True),
        sa.Column("fio", sa.String(255), nullable=False),
        sa.Column("territory", sa.String(255), nullable=True),
        sa.Column("department_1c", sa.String(255), nullable=True),
        sa.Column("position_1c", sa.String(255), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("citizenship", sa.String(64), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("fire_date", sa.Date(), nullable=True),
        sa.Column("state", sa.String(64), nullable=True),
        sa.Column("hourly_rate", sa.Float(), nullable=True),
        sa.Column("fire_reason", sa.Text(), nullable=True),
        sa.Column("fired_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("fired_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- Transfers ---
    op.create_table(
        "transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("from_territory", sa.String(255), nullable=True),
        sa.Column("to_territory", sa.String(255), nullable=True),
        sa.Column("to_site_code", sa.String(64), nullable=True),
        sa.Column("to_site_name", sa.String(255), nullable=True),
        sa.Column("transfer_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'planned'")),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- Registry Imports ---
    op.create_table(
        "registry_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_half", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("added", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("skipped", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("errors_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_preview", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default=sa.text("1"), nullable=False),
    )

    # --- Registry Scores ---
    op.create_table(
        "registry_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("registry_import_id", sa.Integer(), sa.ForeignKey("registry_imports.id"), nullable=False, index=True),
        sa.Column("tab_no", sa.String(64), nullable=False, index=True),
        sa.Column("fio", sa.String(255), nullable=False),
        sa.Column("territory", sa.String(255), nullable=True),
        sa.Column("position", sa.String(255), nullable=True),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("master_fio", sa.String(255), nullable=True),
        # 12 критериев первой оценки
        sa.Column("c1_first", sa.Integer(), nullable=True),
        sa.Column("c2_first", sa.Integer(), nullable=True),
        sa.Column("c3_first", sa.Integer(), nullable=True),
        sa.Column("c4_first", sa.Integer(), nullable=True),
        sa.Column("c5_first", sa.Integer(), nullable=True),
        sa.Column("c6_first", sa.Integer(), nullable=True),
        sa.Column("c7_first", sa.Integer(), nullable=True),
        sa.Column("c8_first", sa.Integer(), nullable=True),
        sa.Column("c9_first", sa.Integer(), nullable=True),
        sa.Column("c10_first", sa.Integer(), nullable=True),
        sa.Column("c11_first", sa.Integer(), nullable=True),
        sa.Column("c12_first", sa.Integer(), nullable=True),
        sa.Column("avg_first", sa.Float(), nullable=True),
        # 12 критериев второй оценки
        sa.Column("c1_second", sa.Integer(), nullable=True),
        sa.Column("c2_second", sa.Integer(), nullable=True),
        sa.Column("c3_second", sa.Integer(), nullable=True),
        sa.Column("c4_second", sa.Integer(), nullable=True),
        sa.Column("c5_second", sa.Integer(), nullable=True),
        sa.Column("c6_second", sa.Integer(), nullable=True),
        sa.Column("c7_second", sa.Integer(), nullable=True),
        sa.Column("c8_second", sa.Integer(), nullable=True),
        sa.Column("c9_second", sa.Integer(), nullable=True),
        sa.Column("c10_second", sa.Integer(), nullable=True),
        sa.Column("c11_second", sa.Integer(), nullable=True),
        sa.Column("c12_second", sa.Integer(), nullable=True),
        sa.Column("avg_second", sa.Float(), nullable=True),
        sa.Column("prod_coeff", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
    )

    # --- Дополнительные колонки (идемпотентно) ---
    conn = op.get_bind()
    
    # must_change_password на users
    try:
        conn.execute(sa.text(
            "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 1"
        ))
    except Exception:
        pass  # уже существует
    
    # token_version на users
    try:
        conn.execute(sa.text(
            "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"
        ))
    except Exception:
        pass  # уже существует


def downgrade() -> None:
    op.drop_table("registry_scores")
    op.drop_table("registry_imports")
    op.drop_table("transfers")
    op.drop_table("fired_employees")
    op.drop_table("import_logs")
    op.drop_table("user_territory_mappings")
    op.drop_table("groups_of_users")
    op.drop_table("departments")
    op.drop_table("territories")
