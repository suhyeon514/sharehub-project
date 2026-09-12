"""특정 차단 건에 대한 소명·이의제기. 취소·자기 심사 허용은 API 정책에서 결정한다."""
from app.extensions import db


class DocumentUnblockRequest(db.Model):
    __tablename__ = "document_unblock_requests"
    __table_args__ = (
        db.UniqueConstraint("pending_block_id", name="uq_unblock_requests_pending_block"),
        db.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_unblock_requests_status",
        ),
        db.CheckConstraint(
            "(status = 'pending' AND reviewed_by_id IS NULL AND review_comment IS NULL "
            "AND reviewed_at IS NULL AND cancelled_at IS NULL) "
            "OR (status IN ('approved', 'rejected') AND reviewed_by_id IS NOT NULL "
            "AND review_comment IS NOT NULL AND reviewed_at IS NOT NULL AND cancelled_at IS NULL) "
            "OR (status = 'cancelled' AND reviewed_by_id IS NULL AND review_comment IS NULL "
            "AND reviewed_at IS NULL AND cancelled_at IS NOT NULL)",
            name="ck_unblock_requests_review_fields",
        ),
        db.Index("ix_unblock_requests_block_time", "block_id", "requested_at"),
        db.Index("ix_unblock_requests_requester_time", "requester_id", "requested_at"),
        db.Index("ix_unblock_requests_status_time", "status", "requested_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    block_id = db.Column(db.Integer, db.ForeignKey("document_blocks.id", ondelete="RESTRICT"), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    request_reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", server_default="pending")
    requested_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    review_comment = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    pending_block_id = db.Column(
        db.Integer,
        db.Computed(
            "CASE WHEN status = 'pending' THEN block_id ELSE NULL END",
            persisted=True,
        ),
        nullable=True,
    )

    block = db.relationship("DocumentBlock", foreign_keys=[block_id])
    requester = db.relationship("User", foreign_keys=[requester_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
