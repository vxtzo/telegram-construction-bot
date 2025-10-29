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
    # Создаем enum типы (если не существуют)
    op.execute("DO $$ BEGIN CREATE TYPE paymentsource AS ENUM ('COMPANY', 'PERSONAL'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE compensationstatus AS ENUM ('PENDING', 'COMPENSATED'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Добавляем колонки в таблицу expenses (если не существуют)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE expenses ADD COLUMN payment_source paymentsource NOT NULL DEFAULT 'COMPANY';
        EXCEPTION WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE expenses ADD COLUMN compensation_status compensationstatus;
        EXCEPTION WHEN duplicate_column THEN null;
        END $$;
    """)


def downgrade() -> None:
    # Удаляем колонки
    op.drop_column('expenses', 'compensation_status')
    op.drop_column('expenses', 'payment_source')
    
    # Удаляем enum типы
    op.execute("DROP TYPE compensationstatus")
    op.execute("DROP TYPE paymentsource")

