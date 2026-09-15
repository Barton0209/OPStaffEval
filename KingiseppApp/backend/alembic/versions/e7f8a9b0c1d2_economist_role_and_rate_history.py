"""economist role and rate history

Шаг 1: роль «Экономист», история изменения ЧТС (rate_history),
поля сотрудника: разряд (category) и дата окончания испытательного срока (probation_end_date).

Примечание: роль добавляется только в Python-енум UserRole (app/models.py).
В SQLite SQLAlchemy реализует sa.Enum как VARCHAR без CHECK-constraint
(проверено: DDL колонок users.role / evaluations.evaluator_role = VARCHAR(10)),
поэтому изменение списка ролей НЕ требует изменения схемы БД.

Revision ID: e7f8a9b0c1d2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-11 03:15:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Разряд сотрудника (из УД-списка / вручную) и дата окончания испытательного срока.
    op.add_column('employees', sa.Column('category', sa.String(length=64), nullable=True))
    op.add_column('employees', sa.Column('probation_end_date', sa.Date(), nullable=True))

    # История изменения ЧТС сотрудника (ведёт экономист).
    op.create_table(
        'rate_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('old_rate', sa.Float(), nullable=True),
        sa.Column('new_rate', sa.Float(), nullable=False),
        sa.Column('changed_at', sa.Date(), nullable=False),
        sa.Column('changed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['changed_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_rate_history_changed_at'), 'rate_history', ['changed_at'], unique=False)
    op.create_index(op.f('ix_rate_history_employee_id'), 'rate_history', ['employee_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_rate_history_employee_id'), table_name='rate_history')
    op.drop_index(op.f('ix_rate_history_changed_at'), table_name='rate_history')
    op.drop_table('rate_history')
    op.drop_column('employees', 'probation_end_date')
    op.drop_column('employees', 'category')