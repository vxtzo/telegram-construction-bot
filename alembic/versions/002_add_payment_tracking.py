"""Add payment tracking to expenses

Revision ID: 002
Revises: 001
Create Date: 2025-10-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаем enum типы
    op.execute("CREATE TYPE paymentsource AS ENUM ('company', 'personal')")
    op.execute("CREATE TYPE compensationstatus AS ENUM ('pending', 'compensated')")
    
    # Добавляем колонки в таблицу expenses
    op.add_column('expenses', sa.Column('payment_source', sa.Enum('company', 'personal', name='paymentsource'), nullable=False, server_default='company'))
    op.add_column('expenses', sa.Column('compensation_status', sa.Enum('pending', 'compensated', name='compensationstatus'), nullable=True))


def downgrade() -> None:
    # Удаляем колонки
    op.drop_column('expenses', 'compensation_status')
    op.drop_column('expenses', 'payment_source')
    
    # Удаляем enum типы
    op.execute("DROP TYPE compensationstatus")
    op.execute("DROP TYPE paymentsource")

