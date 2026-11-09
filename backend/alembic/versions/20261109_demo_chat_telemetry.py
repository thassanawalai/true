"""Add tenant telemetry and ticket-linked chat without changing existing tables.

Revision ID: 20261109_demo
Revises: 0ca6d68be46d
"""
from alembic import op
import sqlalchemy as sa

revision = '20261109_demo'
down_revision = '0ca6d68be46d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('customer_assets',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('company_id', sa.UUID(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=False),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('asset_type', sa.String(64), nullable=False),
        sa.UniqueConstraint('company_id', 'ip_address', name='uq_asset_company_ip'))
    op.create_index('ix_customer_assets_company_id', 'customer_assets', ['company_id'])
    op.create_table('log_collectors',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('company_id', sa.UUID(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('site', sa.String(255), nullable=False),
        sa.UniqueConstraint('company_id', 'name', name='uq_collector_company_name'))
    op.create_index('ix_log_collectors_company_id', 'log_collectors', ['company_id'])
    op.create_table('customer_logs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('company_id', sa.UUID(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('asset_id', sa.UUID(), sa.ForeignKey('customer_assets.id'), nullable=False),
        sa.Column('collector_id', sa.UUID(), sa.ForeignKey('log_collectors.id'), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(), nullable=False))
    op.create_index('ix_customer_logs_company_id', 'customer_logs', ['company_id'])
    op.create_table('chat_rooms',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('owner_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('company_id', sa.UUID(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('ticket_id', sa.UUID(), sa.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('ticket_id'))
    op.create_index('ix_chat_rooms_owner_id', 'chat_rooms', ['owner_id'])
    op.create_index('ix_chat_rooms_company_id', 'chat_rooms', ['company_id'])
    op.create_table('room_messages',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('room_id', sa.UUID(), sa.ForeignKey('chat_rooms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('sender_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('sender_name', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_room_messages_room_id', 'room_messages', ['room_id'])


def downgrade():
    # Avoid accidental deletion of demo tickets' conversation history/telemetry.
    raise RuntimeError('This additive demo revision has no automatic destructive downgrade.')
