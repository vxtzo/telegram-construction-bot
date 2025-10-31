"""Add document-specific file types

Revision ID: 005
Revises: 004
Create Date: 2025-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_enum_value(bind, enum_name: str, value: str) -> None:
    safe_enum = enum_name.replace("'", "''")
    safe_value = value.replace("'", "''")
    statement = f"""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            WHERE t.typname = '{safe_enum}' AND e.enumlabel = '{safe_value}'
        ) THEN
            EXECUTE 'ALTER TYPE ' || quote_ident('{safe_enum}') || ' ADD VALUE ' || quote_literal('{safe_value}');
        END IF;
    END;
    $$;
    """
    bind.execute(sa.text(statement))


def upgrade() -> None:
    bind = op.get_bind()
    for value in ("estimate", "payroll"):
        _add_enum_value(bind, "filetype", value)


def downgrade() -> None:
    # Удаление значений из ENUM в PostgreSQL проблематично,
    # поэтому оставляем downgrade пустым.
    pass


