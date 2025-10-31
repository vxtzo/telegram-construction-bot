"""Add tables for company expenses

Revision ID: 004
Revises: 003
Create Date: 2025-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_index(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    existing = {idx['name'] for idx in inspector.get_indexes(table_name)} if inspector.has_table(table_name) else set()
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table('company_expenses'):
        op.create_table(
            'company_expenses',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('category', sa.String(length=255), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('date', sa.DateTime(), nullable=False),
            sa.Column('added_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_company_expenses_category', 'company_expenses', ['category'])
        op.create_index('ix_company_expenses_date', 'company_expenses', ['date'])
    else:
        inspector = inspect(bind)
        _ensure_index(inspector, 'company_expenses', 'ix_company_expenses_category', ['category'])
        _ensure_index(inspector, 'company_expenses', 'ix_company_expenses_date', ['date'])

    if not inspector.has_table('company_recurring_expenses'):
        op.create_table(
            'company_recurring_expenses',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('category', sa.String(length=255), nullable=False),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('day_of_month', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('start_month', sa.Integer(), nullable=False),
            sa.Column('start_year', sa.Integer(), nullable=False),
            sa.Column('end_month', sa.Integer(), nullable=True),
            sa.Column('end_year', sa.Integer(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('added_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        )
        op.alter_column('company_recurring_expenses', 'day_of_month', server_default=None)
    else:
        columns = {col['name'] for col in inspector.get_columns('company_recurring_expenses')}

        if 'start_month' not in columns and 'period_month' in columns:
            op.alter_column('company_recurring_expenses', 'period_month', new_column_name='start_month')
        elif 'start_month' not in columns:
            op.add_column(
                'company_recurring_expenses',
                sa.Column('start_month', sa.Integer(), nullable=False, server_default='1'),
            )
            op.alter_column('company_recurring_expenses', 'start_month', server_default=None)

        if 'start_year' not in columns and 'period_year' in columns:
            op.alter_column('company_recurring_expenses', 'period_year', new_column_name='start_year')
        elif 'start_year' not in columns:
            op.add_column(
                'company_recurring_expenses',
                sa.Column('start_year', sa.Integer(), nullable=False, server_default=sa.text('EXTRACT(YEAR FROM CURRENT_TIMESTAMP)::int')),
            )
            op.alter_column('company_recurring_expenses', 'start_year', server_default=None)

        columns = {col['name'] for col in inspector.get_columns('company_recurring_expenses')}

        if 'day_of_month' not in columns:
            op.add_column(
                'company_recurring_expenses',
                sa.Column('day_of_month', sa.Integer(), nullable=False, server_default='1'),
            )
            op.alter_column('company_recurring_expenses', 'day_of_month', server_default=None)

        if 'end_month' not in columns:
            op.add_column('company_recurring_expenses', sa.Column('end_month', sa.Integer(), nullable=True))
        if 'end_year' not in columns:
            op.add_column('company_recurring_expenses', sa.Column('end_year', sa.Integer(), nullable=True))
        if 'is_active' not in columns:
            op.add_column(
                'company_recurring_expenses',
                sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            )
            op.alter_column('company_recurring_expenses', 'is_active', server_default=None)
    inspector = inspect(bind)
    _ensure_index(inspector, 'company_recurring_expenses', 'ix_company_recurring_expenses_category', ['category'])

    if not inspector.has_table('company_expense_logs'):
        op.create_table(
            'company_expense_logs',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('expense_type', sa.String(length=50), nullable=False),
            sa.Column('entity_id', sa.Integer(), nullable=False),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index('ix_company_expense_logs_type', 'company_expense_logs', ['expense_type'])
        op.create_index('ix_company_expense_logs_entity', 'company_expense_logs', ['entity_id'])
        op.create_index('ix_company_expense_logs_created_at', 'company_expense_logs', ['created_at'])
        op.create_index(
            'ix_company_expense_logs_type_entity',
            'company_expense_logs',
            ['expense_type', 'entity_id']
        )
    else:
        inspector = inspect(bind)
        _ensure_index(inspector, 'company_expense_logs', 'ix_company_expense_logs_type', ['expense_type'])
        _ensure_index(inspector, 'company_expense_logs', 'ix_company_expense_logs_entity', ['entity_id'])
        _ensure_index(inspector, 'company_expense_logs', 'ix_company_expense_logs_created_at', ['created_at'])
        _ensure_index(inspector, 'company_expense_logs', 'ix_company_expense_logs_type_entity', ['expense_type', 'entity_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table('company_expense_logs'):
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('company_expense_logs')}
        for index_name in [
            'ix_company_expense_logs_type_entity',
            'ix_company_expense_logs_created_at',
            'ix_company_expense_logs_entity',
            'ix_company_expense_logs_type',
        ]:
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name='company_expense_logs')
        op.drop_table('company_expense_logs')

    if inspector.has_table('company_recurring_expenses'):
        columns = {col['name'] for col in inspector.get_columns('company_recurring_expenses')}
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('company_recurring_expenses')}
        if 'ix_company_recurring_expenses_category' in existing_indexes:
            op.drop_index('ix_company_recurring_expenses_category', table_name='company_recurring_expenses')

        if 'is_active' in columns:
            op.drop_column('company_recurring_expenses', 'is_active')
        if 'end_year' in columns:
            op.drop_column('company_recurring_expenses', 'end_year')
        if 'end_month' in columns:
            op.drop_column('company_recurring_expenses', 'end_month')
        if 'day_of_month' in columns:
            op.drop_column('company_recurring_expenses', 'day_of_month')

        columns = {col['name'] for col in inspector.get_columns('company_recurring_expenses')}
        if 'start_year' in columns and 'period_year' not in columns:
            op.alter_column('company_recurring_expenses', 'start_year', new_column_name='period_year')
        if 'start_month' in columns and 'period_month' not in columns:
            op.alter_column('company_recurring_expenses', 'start_month', new_column_name='period_month')

        op.drop_table('company_recurring_expenses')

    if inspector.has_table('company_expenses'):
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('company_expenses')}
        for index_name in ['ix_company_expenses_category', 'ix_company_expenses_date']:
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name='company_expenses')
        op.drop_table('company_expenses')
