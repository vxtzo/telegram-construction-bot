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
    """Приводим существующие значения к верхнему регистру и пересоздаем enum."""

    # Преобразуем колонки к text, чтобы можно было безопасно обновлять enum
    op.execute("ALTER TABLE expenses ALTER COLUMN payment_source TYPE text USING payment_source::text")
    op.execute("ALTER TABLE expenses ALTER COLUMN compensation_status TYPE text USING compensation_status::text")

    # Удаляем старые enum типы, если они есть
    op.execute("DROP TYPE IF EXISTS paymentsource CASCADE")
    op.execute("DROP TYPE IF EXISTS compensationstatus CASCADE")

    # Создаем новые enum типы с верхним регистром
    op.execute("CREATE TYPE paymentsource AS ENUM ('COMPANY', 'PERSONAL')")
    op.execute("CREATE TYPE compensationstatus AS ENUM ('PENDING', 'COMPENSATED')")

    # Обновляем существующие значения, если они в нижнем регистре
    op.execute("UPDATE expenses SET payment_source = UPPER(payment_source) WHERE payment_source IS NOT NULL")
    op.execute("UPDATE expenses SET compensation_status = UPPER(compensation_status) WHERE compensation_status IS NOT NULL")

    # Приводим колонки обратно к enum типу
    op.execute(
        "ALTER TABLE expenses ALTER COLUMN payment_source TYPE paymentsource USING payment_source::paymentsource"
    )
    op.execute(
        "ALTER TABLE expenses ALTER COLUMN compensation_status TYPE compensationstatus USING compensation_status::compensationstatus"
    )

    # Устанавливаем значение по умолчанию
    op.execute("ALTER TABLE expenses ALTER COLUMN payment_source SET DEFAULT 'COMPANY'")


def downgrade() -> None:
    """Возвращаем enum значения в нижний регистр."""

    op.execute("ALTER TABLE expenses ALTER COLUMN payment_source DROP DEFAULT")

    # Преобразуем в text перед пересозданием enum
    op.execute("ALTER TABLE expenses ALTER COLUMN payment_source TYPE text USING payment_source::text")
    op.execute("ALTER TABLE expenses ALTER COLUMN compensation_status TYPE text USING compensation_status::text")

    # Удаляем текущие enum типы
    op.execute("DROP TYPE IF EXISTS paymentsource CASCADE")
    op.execute("DROP TYPE IF EXISTS compensationstatus CASCADE")

    # Создаем enum с нижним регистром
    op.execute("CREATE TYPE paymentsource AS ENUM ('company', 'personal')")
    op.execute("CREATE TYPE compensationstatus AS ENUM ('pending', 'compensated')")

    # Преобразуем значения обратно в нижний регистр
    op.execute("UPDATE expenses SET payment_source = LOWER(payment_source) WHERE payment_source IS NOT NULL")
    op.execute(
        "UPDATE expenses SET compensation_status = LOWER(compensation_status) WHERE compensation_status IS NOT NULL"
    )

    # Возвращаем типы колонкам
    op.execute(
        "ALTER TABLE expenses ALTER COLUMN payment_source TYPE paymentsource USING payment_source::paymentsource"
    )
    op.execute(
        "ALTER TABLE expenses ALTER COLUMN compensation_status TYPE compensationstatus USING compensation_status::compensationstatus"
    )

    op.execute("ALTER TABLE expenses ALTER COLUMN payment_source SET DEFAULT 'company'")

