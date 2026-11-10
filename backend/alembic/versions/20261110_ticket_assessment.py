"""Persist ticket assessment provenance and reasoning.

Revision ID: 20261110_ticket_assessment
Revises: 20261109_demo
"""
import sqlalchemy as sa
from alembic import op

revision = '20261110_ticket_assessment'
down_revision = '20261109_demo'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ticket_assessments',
        sa.Column('ticket_id', sa.UUID(), sa.ForeignKey('tickets.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('model', sa.String()),
        sa.Column('incident_type', sa.String(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('recommendation', sa.Text(), nullable=False),
        sa.Column('fallback_reason', sa.String()),
        sa.Column('priority_policy', sa.String(), nullable=False),
    )


def downgrade():
    op.drop_table('ticket_assessments')
