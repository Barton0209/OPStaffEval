"""tariff grid and rate_last_raised

Revision ID: a1b2c3d4e5f6
Revises: 2cf3afa55a9d
Create Date: 2026-09-09 04:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '2cf3afa55a9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Дата последнего поднятия ЧТС (из УД-списка .xlsb / ручное изменение).
    op.add_column('employees', sa.Column('rate_last_raised', sa.Date(), nullable=True))
    # Гражданство сотрудника (из УД-списка) — для сопоставления с тарифной сеткой.
    op.add_column('employees', sa.Column('citizenship', sa.String(length=64), nullable=True))

    # Тарифная сетка: мин/макс ЧТС по (должность, гражданство).
    op.create_table(
        'tariff_grids',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('position', sa.String(length=255), nullable=False),
        sa.Column('citizenship', sa.String(length=64), nullable=False),
        sa.Column('min_rate', sa.Float(), nullable=False),
        sa.Column('max_rate', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('position', 'citizenship', name='uq_tariff_position_citizenship'),
    )
    op.create_index(op.f('ix_tariff_grids_citizenship'), 'tariff_grids', ['citizenship'], unique=False)
    op.create_index(op.f('ix_tariff_grids_position'), 'tariff_grids', ['position'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tariff_grids_position'), table_name='tariff_grids')
    op.drop_index(op.f('ix_tariff_grids_citizenship'), table_name='tariff_grids')
    op.drop_table('tariff_grids')
    op.drop_column('employees', 'citizenship')
    op.drop_column('employees', 'rate_last_raised')