"""Initial migration for LookBot v2.

This migration creates all the necessary tables for the application based on the services
and models we've implemented.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_admin', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)
    )

    # API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('key_name', sa.String(50), nullable=False),
        sa.Column('api_key', sa.String(255), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow)
    )

    # Watchlists table
    op.create_table(
        'watchlists',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)
    )

    # Watchlist Items table
    op.create_table(
        'watchlist_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('watchlist_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('watchlists.id')),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('added_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('notes', sa.Text()),
        sa.Column('alert_price', sa.Float()),
        sa.Column('alert_condition', sa.String(20))
    )

    # Topics table
    op.create_table(
        'topics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)
    )

    # Topic Keywords table
    op.create_table(
        'topic_keywords',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('topics.id')),
        sa.Column('keyword', sa.String(100), nullable=False),
        sa.Column('weight', sa.Float(), default=1.0)
    )

    # News Articles table
    op.create_table(
        'news_articles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('url', sa.String(1000), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('sentiment_score', sa.Float()),
        sa.Column('impact_score', sa.Float()),
        sa.Column('content_hash', sa.String(64), unique=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow)
    )

    # Article Topics table
    op.create_table(
        'article_topics',
        sa.Column('article_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('news_articles.id')),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('topics.id')),
        sa.Column('relevance_score', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('article_id', 'topic_id')
    )

    # Article Symbols table
    op.create_table(
        'article_symbols',
        sa.Column('article_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('news_articles.id')),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('mention_count', sa.Integer(), default=1),
        sa.PrimaryKeyConstraint('article_id', 'symbol')
    )

    # Technical Analysis table
    op.create_table(
        'technical_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('timeframe', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('indicators', postgresql.JSONB(), nullable=False),
        sa.Column('signals', postgresql.JSONB(), nullable=False),
        sa.Column('patterns', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow)
    )

    # Order Flow Analysis table
    op.create_table(
        'order_flow_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('timeframe', sa.String(20), nullable=False),
        sa.Column('volume_profile', postgresql.JSONB()),
        sa.Column('trades', postgresql.JSONB()),
        sa.Column('imbalances', postgresql.JSONB()),
        sa.Column('metrics', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow)
    )

    # Dark Pool Activity table
    op.create_table(
        'dark_pool_activity',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('venue', sa.String(50), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=False),
        sa.Column('trade_count', sa.Integer()),
        sa.Column('is_block_trade', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow)
    )

    # Options Flow table
    op.create_table(
        'options_flow',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('expiration', sa.Date(), nullable=False),
        sa.Column('strike', sa.Float(), nullable=False),
        sa.Column('option_type', sa.String(4), nullable=False),
        sa.Column('trade_type', sa.String(20), nullable=False),
        sa.Column('volume', sa.Integer(), nullable=False),
        sa.Column('open_interest', sa.Integer()),
        sa.Column('premium', sa.Float()),
        sa.Column('implied_volatility', sa.Float()),
        sa.Column('delta', sa.Float()),
        sa.Column('gamma', sa.Float()),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow)
    )

    # Notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSONB()),
        sa.Column('is_read', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow)
    )

    # Backtest Results table
    op.create_table(
        'backtest_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('strategy_name', sa.String(100), nullable=False),
        sa.Column('parameters', postgresql.JSONB(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('symbols', postgresql.ARRAY(sa.String(20)), nullable=False),
        sa.Column('trades', postgresql.JSONB()),
        sa.Column('metrics', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow)
    )

    # Create indexes
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_watchlist_items_symbol', 'watchlist_items', ['symbol'])
    op.create_index('ix_news_articles_published_at', 'news_articles', ['published_at'])
    op.create_index('ix_technical_analysis_symbol_timeframe', 'technical_analysis', ['symbol', 'timeframe'])
    op.create_index('ix_order_flow_analysis_symbol_timestamp', 'order_flow_analysis', ['symbol', 'timestamp'])
    op.create_index('ix_dark_pool_activity_symbol_timestamp', 'dark_pool_activity', ['symbol', 'timestamp'])
    op.create_index('ix_options_flow_symbol_expiration', 'options_flow', ['symbol', 'expiration'])
    op.create_index('ix_notifications_user_id_created_at', 'notifications', ['user_id', 'created_at'])

def downgrade():
    # Drop tables in reverse order to handle dependencies
    op.drop_table('backtest_results')
    op.drop_table('notifications')
    op.drop_table('options_flow')
    op.drop_table('dark_pool_activity')
    op.drop_table('order_flow_analysis')
    op.drop_table('technical_analysis')
    op.drop_table('article_symbols')
    op.drop_table('article_topics')
    op.drop_table('news_articles')
    op.drop_table('topic_keywords')
    op.drop_table('topics')
    op.drop_table('watchlist_items')
    op.drop_table('watchlists')
    op.drop_table('api_keys')
    op.drop_table('users')
