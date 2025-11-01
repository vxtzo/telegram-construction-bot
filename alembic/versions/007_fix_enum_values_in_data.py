"""Fix enum values in existing data - convert to lowercase

Revision ID: 007
Revises: 006
Create Date: 2025-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Обновляем значения в таблице users: ADMIN -> admin, FOREMAN -> foreman
    op.execute("""
        UPDATE users 
        SET role = LOWER(role::text)::userrole 
        WHERE role::text IN ('ADMIN', 'FOREMAN')
    """)
    
    # Обновляем значения в таблице expenses: SUPPLIES -> supplies, TRANSPORT -> transport, OVERHEAD -> overhead
    op.execute("""
        UPDATE expenses 
        SET type = LOWER(type::text)::expensetype 
        WHERE type::text IN ('SUPPLIES', 'TRANSPORT', 'OVERHEAD')
    """)
    
    # Обновляем payment_source: COMPANY -> company, PERSONAL -> personal
    op.execute("""
        UPDATE expenses 
        SET payment_source = LOWER(payment_source::text)::paymentsource 
        WHERE payment_source::text IN ('COMPANY', 'PERSONAL')
    """)
    
    # Обновляем compensation_status: PENDING -> pending, COMPENSATED -> compensated
    op.execute("""
        UPDATE expenses 
        SET compensation_status = LOWER(compensation_status::text)::compensationstatus 
        WHERE compensation_status::text IN ('PENDING', 'COMPENSATED')
    """)
    
    # Обновляем file_type: PHOTO -> photo, RECEIPT -> receipt, DOCUMENT -> document, ESTIMATE -> estimate, PAYROLL -> payroll
    op.execute("""
        UPDATE files 
        SET file_type = LOWER(file_type::text)::filetype 
        WHERE file_type::text IN ('PHOTO', 'RECEIPT', 'DOCUMENT', 'ESTIMATE', 'PAYROLL')
    """)
    
    # Обновляем object_logs action: все типы в нижний регистр
    op.execute("""
        UPDATE object_logs 
        SET action = LOWER(action::text)::objectlogtype
    """)


def downgrade() -> None:
    # Откат к верхнему регистру
    op.execute("""
        UPDATE users 
        SET role = UPPER(role::text)::userrole 
        WHERE role::text IN ('admin', 'foreman')
    """)
    
    op.execute("""
        UPDATE expenses 
        SET type = UPPER(type::text)::expensetype 
        WHERE type::text IN ('supplies', 'transport', 'overhead')
    """)
    
    op.execute("""
        UPDATE expenses 
        SET payment_source = UPPER(payment_source::text)::paymentsource 
        WHERE payment_source::text IN ('company', 'personal')
    """)
    
    op.execute("""
        UPDATE expenses 
        SET compensation_status = UPPER(compensation_status::text)::compensationstatus 
        WHERE compensation_status::text IN ('pending', 'compensated')
    """)
    
    op.execute("""
        UPDATE files 
        SET file_type = UPPER(file_type::text)::filetype 
        WHERE file_type::text IN ('photo', 'receipt', 'document', 'estimate', 'payroll')
    """)
    
    op.execute("""
        UPDATE object_logs 
        SET action = UPPER(action::text)::objectlogtype
    """)

