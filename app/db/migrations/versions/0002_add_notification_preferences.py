"""add notification preferences

Revision ID: 0002
Revises: 0001
Create Date: 2024-12-28 13:04:23.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to users table
    op.add_column('users', sa.Column('email', sa.String(), nullable=True))
    op.add_column('users', sa.Column('full_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column(
        'notification_preferences',
        postgresql.JSONB(),
        nullable=False,
        server_default=sa.text("""
            '{
                "email_enabled": true,
                "sms_enabled": true,
                "push_enabled": true,
                "webhook_enabled": true,
                "alert_types": {
                    "price": true,
                    "volume": true,
                    "news": true,
                    "technical": true,
                    "filings": true,
                    "social": true
                },
                "quiet_hours": {
                    "start": "22:00",
                    "end": "08:00"
                },
                "priority_threshold": "medium"
            }'::jsonb
        """)
    ))

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=True),
        sa.Column('priority', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('read', sa.Boolean(), nullable=False, default=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.Index('ix_notifications_user_id', 'user_id'),
        sa.Index('ix_notifications_created_at', 'created_at'),
        sa.Index('ix_notifications_read', 'read'),
        sa.Index('ix_notifications_type', 'type')
    )

    # Create user_devices table for push tokens
    op.create_table(
        'user_devices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_token', sa.String(), nullable=False),
        sa.Column('device_type', sa.String(), nullable=False),  # ios, android, web
        sa.Column('device_name', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('device_token'),
        sa.Index('ix_user_devices_user_id', 'user_id'),
        sa.Index('ix_user_devices_device_token', 'device_token'),
        sa.Index('ix_user_devices_is_active', 'is_active')
    )

    # Create webhook_endpoints table
    op.create_table(
        'webhook_endpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('secret', sa.String(), nullable=False),  # For webhook signature
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('failure_count', sa.Integer(), nullable=False, default=0),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.Index('ix_webhook_endpoints_user_id', 'user_id'),
        sa.Index('ix_webhook_endpoints_is_active', 'is_active')
    )


def downgrade():
    op.drop_table('webhook_endpoints')
    op.drop_table('user_devices')
    op.drop_table('notifications')
    op.drop_column('users', 'notification_preferences')
    op.drop_column('users', 'full_name')
    op.drop_column('users', 'email')
