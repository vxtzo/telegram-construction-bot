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


def rename_enum_value(enum_name: str, old_value: str, new_value: str) -> None:
    """Безопасно переименовывает значение enum, если оно существует."""

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = '{enum_name}' AND e.enumlabel = '{old_value}'
            ) THEN
                ALTER TYPE {enum_name} RENAME VALUE '{old_value}' TO '{new_value}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    """Переименовываем значения enum в верхний регистр."""

    # Переименовываем значения payment_source
    rename_enum_value('paymentsource', 'company', 'COMPANY')
    rename_enum_value('paymentsource', 'personal', 'PERSONAL')

    # Переименовываем значения compensation_status
    rename_enum_value('compensationstatus', 'pending', 'PENDING')
    rename_enum_value('compensationstatus', 'compensated', 'COMPENSATED')

    # Обновляем значение по умолчанию
    op.execute("ALTER TABLE expenses ALTER COLUMN payment_source SET DEFAULT 'COMPANY'")


def downgrade() -> None:
    """Возвращаем значения enum в нижний регистр."""

    op.execute("ALTER TABLE expenses ALTER COLUMN payment_source SET DEFAULT 'company'")

    rename_enum_value('paymentsource', 'COMPANY', 'company')
    rename_enum_value('paymentsource', 'PERSONAL', 'personal')

    rename_enum_value('compensationstatus', 'PENDING', 'pending')
    rename_enum_value('compensationstatus', 'COMPENSATED', 'compensated')

