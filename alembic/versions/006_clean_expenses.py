"""Clean all existing company expenses

Revision ID: 006
Revises: 005
Create Date: 2025-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Удаляем все разовые расходы
    op.execute("DELETE FROM company_expenses")
    
    # Удаляем все постоянные расходы
    op.execute("DELETE FROM company_recurring_expenses")
    
    # Удаляем логи (опционально, чтобы начать с чистого листа)
    op.execute("DELETE FROM company_expense_logs")


def downgrade() -> None:
    # Откат невозможен - данные удалены
    pass

