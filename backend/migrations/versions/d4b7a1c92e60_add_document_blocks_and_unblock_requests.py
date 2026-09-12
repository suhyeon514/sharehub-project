"""Add document blocks and unblock requests.

Revision ID: d4b7a1c92e60
Revises: ca9615ef4c1e

Generated from model metadata without connecting to the application database.
"""
from alembic import op
import sqlalchemy as sa

revision = "d4b7a1c92e60"
down_revision = "ca9615ef4c1e"
branch_labels = None
depends_on = None


def upgrade():
    # Create the parent table before its requests.
    op.create_table('document_blocks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=True),
    sa.Column('document_id_snapshot', sa.Integer(), nullable=False),
    sa.Column('blocked_by_id', sa.Integer(), nullable=False),
    sa.Column('block_reason', sa.Text(), nullable=False),
    sa.Column('block_basis', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='blocked', nullable=False),
    sa.Column('blocked_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('unblocked_by_id', sa.Integer(), nullable=True),
    sa.Column('unblock_reason', sa.Text(), nullable=True),
    sa.Column('unblocked_at', sa.DateTime(), nullable=True),
    sa.Column('active_document_id', sa.Integer(), sa.Computed("CASE WHEN status = 'blocked' THEN document_id ELSE NULL END", persisted=True), nullable=True),
    sa.CheckConstraint("(status = 'blocked' AND document_id IS NOT NULL AND unblocked_by_id IS NULL AND unblocked_at IS NULL AND unblock_reason IS NULL) OR (status = 'unblocked' AND unblocked_by_id IS NOT NULL AND unblocked_at IS NOT NULL AND unblock_reason IS NOT NULL)", name='ck_document_blocks_release_fields'),
    sa.CheckConstraint("status IN ('blocked', 'unblocked')", name='ck_document_blocks_status'),
    sa.CheckConstraint('document_id IS NULL OR document_id = document_id_snapshot', name='ck_document_blocks_document_snapshot'),
    sa.ForeignKeyConstraint(['blocked_by_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['unblocked_by_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('active_document_id', name='uq_document_blocks_active_document')
    )
    op.create_index('ix_document_blocks_document_time', 'document_blocks', ['document_id', 'blocked_at'], unique=False)
    op.create_index('ix_document_blocks_status_time', 'document_blocks', ['status', 'blocked_at'], unique=False)
    op.create_table('document_unblock_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('block_id', sa.Integer(), nullable=False),
    sa.Column('requester_id', sa.Integer(), nullable=False),
    sa.Column('request_reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('requested_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
    sa.Column('review_comment', sa.Text(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(), nullable=True),
    sa.Column('pending_block_id', sa.Integer(), sa.Computed("CASE WHEN status = 'pending' THEN block_id ELSE NULL END", persisted=True), nullable=True),
    sa.CheckConstraint("(status = 'pending' AND reviewed_by_id IS NULL AND review_comment IS NULL AND reviewed_at IS NULL AND cancelled_at IS NULL) OR (status IN ('approved', 'rejected') AND reviewed_by_id IS NOT NULL AND review_comment IS NOT NULL AND reviewed_at IS NOT NULL AND cancelled_at IS NULL) OR (status = 'cancelled' AND reviewed_by_id IS NULL AND review_comment IS NULL AND reviewed_at IS NULL AND cancelled_at IS NOT NULL)", name='ck_unblock_requests_review_fields'),
    sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name='ck_unblock_requests_status'),
    sa.ForeignKeyConstraint(['block_id'], ['document_blocks.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pending_block_id', name='uq_unblock_requests_pending_block')
    )
    op.create_index('ix_unblock_requests_block_time', 'document_unblock_requests', ['block_id', 'requested_at'], unique=False)
    op.create_index('ix_unblock_requests_requester_time', 'document_unblock_requests', ['requester_id', 'requested_at'], unique=False)
    op.create_index('ix_unblock_requests_status_time', 'document_unblock_requests', ['status', 'requested_at'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # Requests reference blocks; preserve this dependency order.
    op.drop_table("document_unblock_requests")
    op.drop_table("document_blocks")
