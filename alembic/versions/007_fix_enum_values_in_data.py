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
    # СНАЧАЛА добавляем новые значения в нижнем регистре к enum типам
    # userrole: добавляем 'admin', 'foreman'
    with op.get_context().autocommit_block():
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'admin' AND enumtypid = 'userrole'::regtype) THEN
                    ALTER TYPE userrole ADD VALUE 'admin';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'foreman' AND enumtypid = 'userrole'::regtype) THEN
                    ALTER TYPE userrole ADD VALUE 'foreman';
                END IF;
            END $$;
        """)
    
    # Обновляем значения в таблице users: ADMIN -> admin, FOREMAN -> foreman
    op.execute("""
        UPDATE users 
        SET role = LOWER(role::text)::userrole 
        WHERE role::text IN ('ADMIN', 'FOREMAN')
    """)
    
    # expensetype: добавляем 'supplies', 'transport', 'overhead'
    with op.get_context().autocommit_block():
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'supplies' AND enumtypid = 'expensetype'::regtype) THEN
                    ALTER TYPE expensetype ADD VALUE 'supplies';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'transport' AND enumtypid = 'expensetype'::regtype) THEN
                    ALTER TYPE expensetype ADD VALUE 'transport';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'overhead' AND enumtypid = 'expensetype'::regtype) THEN
                    ALTER TYPE expensetype ADD VALUE 'overhead';
                END IF;
            END $$;
        """)
    
    # Обновляем значения в таблице expenses: SUPPLIES -> supplies, TRANSPORT -> transport, OVERHEAD -> overhead
    op.execute("""
        UPDATE expenses 
        SET type = LOWER(type::text)::expensetype 
        WHERE type::text IN ('SUPPLIES', 'TRANSPORT', 'OVERHEAD')
    """)
    
    # paymentsource: добавляем 'company', 'personal'
    with op.get_context().autocommit_block():
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'company' AND enumtypid = 'paymentsource'::regtype) THEN
                    ALTER TYPE paymentsource ADD VALUE 'company';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'personal' AND enumtypid = 'paymentsource'::regtype) THEN
                    ALTER TYPE paymentsource ADD VALUE 'personal';
                END IF;
            END $$;
        """)
    
    # Обновляем payment_source: COMPANY -> company, PERSONAL -> personal
    op.execute("""
        UPDATE expenses 
        SET payment_source = LOWER(payment_source::text)::paymentsource 
        WHERE payment_source::text IN ('COMPANY', 'PERSONAL')
    """)
    
    # compensationstatus: добавляем 'pending', 'compensated'
    with op.get_context().autocommit_block():
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'pending' AND enumtypid = 'compensationstatus'::regtype) THEN
                    ALTER TYPE compensationstatus ADD VALUE 'pending';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'compensated' AND enumtypid = 'compensationstatus'::regtype) THEN
                    ALTER TYPE compensationstatus ADD VALUE 'compensated';
                END IF;
            END $$;
        """)
    
    # Обновляем compensation_status: PENDING -> pending, COMPENSATED -> compensated
    op.execute("""
        UPDATE expenses 
        SET compensation_status = LOWER(compensation_status::text)::compensationstatus 
        WHERE compensation_status::text IN ('PENDING', 'COMPENSATED')
    """)
    
    # filetype: добавляем 'photo', 'receipt', 'document' (estimate и payroll уже добавлены ранее)
    with op.get_context().autocommit_block():
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'photo' AND enumtypid = 'filetype'::regtype) THEN
                    ALTER TYPE filetype ADD VALUE 'photo';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'receipt' AND enumtypid = 'filetype'::regtype) THEN
                    ALTER TYPE filetype ADD VALUE 'receipt';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'document' AND enumtypid = 'filetype'::regtype) THEN
                    ALTER TYPE filetype ADD VALUE 'document';
                END IF;
            END $$;
        """)
    
    # Обновляем file_type: PHOTO -> photo, RECEIPT -> receipt, DOCUMENT -> document, ESTIMATE -> estimate, PAYROLL -> payroll
    op.execute("""
        UPDATE files 
        SET file_type = LOWER(file_type::text)::filetype 
        WHERE file_type::text IN ('PHOTO', 'RECEIPT', 'DOCUMENT', 'ESTIMATE', 'PAYROLL')
    """)
    
    # objectlogtype: добавляем все значения в нижнем регистре
    with op.get_context().autocommit_block():
        op.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'expense_created' AND enumtypid = 'objectlogtype'::regtype) THEN
                    ALTER TYPE objectlogtype ADD VALUE 'expense_created';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'expense_updated' AND enumtypid = 'objectlogtype'::regtype) THEN
                    ALTER TYPE objectlogtype ADD VALUE 'expense_updated';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'expense_deleted' AND enumtypid = 'objectlogtype'::regtype) THEN
                    ALTER TYPE objectlogtype ADD VALUE 'expense_deleted';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'expense_compensated' AND enumtypid = 'objectlogtype'::regtype) THEN
                    ALTER TYPE objectlogtype ADD VALUE 'expense_compensated';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'advance_created' AND enumtypid = 'objectlogtype'::regtype) THEN
                    ALTER TYPE objectlogtype ADD VALUE 'advance_created';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'advance_updated' AND enumtypid = 'objectlogtype'::regtype) THEN
                    ALTER TYPE objectlogtype ADD VALUE 'advance_updated';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'advance_deleted' AND enumtypid = 'objectlogtype'::regtype) THEN
                    ALTER TYPE objectlogtype ADD VALUE 'advance_deleted';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'object_completed' AND enumtypid = 'objectlogtype'::regtype) THEN
                    ALTER TYPE objectlogtype ADD VALUE 'object_completed';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'object_restored' AND enumtypid = 'objectlogtype'::regtype) THEN
                    ALTER TYPE objectlogtype ADD VALUE 'object_restored';
                END IF;
            END $$;
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

