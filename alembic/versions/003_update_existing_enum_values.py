"""Update existing enum values to uppercase

Revision ID: 003
Revises: 002
Create Date: 2025-10-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Обновляем существующие данные в нижнем регистре на верхний
    
    # Сначала удаляем старые enum типы и создаем новые с правильными значениями
    op.execute("""
        -- Временно меняем тип колонок на text
        ALTER TABLE expenses ALTER COLUMN payment_source TYPE text;
        ALTER TABLE expenses ALTER COLUMN compensation_status TYPE text;
        
        -- Удаляем старые enum типы если существуют
        DROP TYPE IF EXISTS paymentsource CASCADE;
        DROP TYPE IF EXISTS compensationstatus CASCADE;
        
        -- Создаем новые enum типы с правильными значениями
        CREATE TYPE paymentsource AS ENUM ('COMPANY', 'PERSONAL');
        CREATE TYPE compensationstatus AS ENUM ('PENDING', 'COMPENSATED');
        
        -- Обновляем существующие значения на верхний регистр
        UPDATE expenses SET payment_source = UPPER(payment_source) WHERE payment_source IS NOT NULL;
        UPDATE expenses SET compensation_status = UPPER(compensation_status) WHERE compensation_status IS NOT NULL;
        
        -- Меняем тип колонок обратно на enum с правильными типами
        ALTER TABLE expenses 
            ALTER COLUMN payment_source TYPE paymentsource USING payment_source::paymentsource;
        
        ALTER TABLE expenses 
            ALTER COLUMN compensation_status TYPE compensationstatus USING compensation_status::compensationstatus;
    """)


def downgrade() -> None:
    # Откатываем обратно на нижний регистр
    op.execute("""
        ALTER TABLE expenses ALTER COLUMN payment_source TYPE text;
        ALTER TABLE expenses ALTER COLUMN compensation_status TYPE text;
        
        DROP TYPE IF EXISTS paymentsource CASCADE;
        DROP TYPE IF EXISTS compensationstatus CASCADE;
        
        CREATE TYPE paymentsource AS ENUM ('company', 'personal');
        CREATE TYPE compensationstatus AS ENUM ('pending', 'compensated');
        
        UPDATE expenses SET payment_source = LOWER(payment_source) WHERE payment_source IS NOT NULL;
        UPDATE expenses SET compensation_status = LOWER(compensation_status) WHERE compensation_status IS NOT NULL;
        
        ALTER TABLE expenses 
            ALTER COLUMN payment_source TYPE paymentsource USING payment_source::paymentsource;
        
        ALTER TABLE expenses 
            ALTER COLUMN compensation_status TYPE compensationstatus USING compensation_status::compensationstatus;
    """)

