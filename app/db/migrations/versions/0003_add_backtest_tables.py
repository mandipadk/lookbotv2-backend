"""add backtest tables

Revision ID: 0003
Revises: 0002
Create Date: 2024-12-28 13:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create backtest_strategies table
    op.create_table(
        'backtest_strategies',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, default=False),
        sa.Column('performance', JSONB(), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create backtest_results table
    op.create_table(
        'backtest_results',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('strategy_id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('config', JSONB(), nullable=False),
        sa.Column('stats', JSONB(), nullable=False),
        sa.Column('equity_curve', JSONB(), nullable=False),
        sa.Column('trades', JSONB(), nullable=False),
        sa.Column('positions', JSONB(), nullable=False),
        sa.Column('orders', JSONB(), nullable=False),
        sa.Column('metrics', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['strategy_id'], ['backtest_strategies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index(
        'ix_backtest_strategies_user_id',
        'backtest_strategies',
        ['user_id']
    )
    op.create_index(
        'ix_backtest_strategies_is_public',
        'backtest_strategies',
        ['is_public']
    )
    op.create_index(
        'ix_backtest_results_strategy_id',
        'backtest_results',
        ['strategy_id']
    )
    op.create_index(
        'ix_backtest_results_user_id',
        'backtest_results',
        ['user_id']
    )


def downgrade() -> None:
    op.drop_table('backtest_results')
    op.drop_table('backtest_strategies')
