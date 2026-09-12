"""문서 차단 건과 해제 이력. DB 적용은 별도 마이그레이션으로 진행한다."""
from app.extensions import db


class DocumentBlock(db.Model):
    __tablename__ = "document_blocks"
    __table_args__ = (
        db.UniqueConstraint("active_document_id", name="uq_document_blocks_active_document"),
        db.CheckConstraint("status IN ('blocked', 'unblocked')", name="ck_document_blocks_status"),
        db.CheckConstraint(
            "document_id IS NULL OR document_id = document_id_snapshot",
            name="ck_document_blocks_document_snapshot",
        ),
        db.CheckConstraint(
            "(status = 'blocked' AND document_id IS NOT NULL "
            "AND unblocked_by_id IS NULL AND unblocked_at IS NULL AND unblock_reason IS NULL) "
            "OR (status = 'unblocked' AND unblocked_by_id IS NOT NULL "
            "AND unblocked_at IS NOT NULL AND unblock_reason IS NOT NULL)",
            name="ck_document_blocks_release_fields",
        ),
        db.Index("ix_document_blocks_document_time", "document_id", "blocked_at"),
        db.Index("ix_document_blocks_status_time", "status", "blocked_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # 삭제 API에서 해제된 이력의 연결을 명시적으로 해제한다. 자동 연쇄 삭제 금지.
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True)
    # 생성 시 서버가 document_id와 같은 값을 저장하고 이후 변경하지 않는다.
    document_id_snapshot = db.Column(db.Integer, nullable=False)
    blocked_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    block_reason = db.Column(db.Text, nullable=False)
    block_basis = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="blocked", server_default="blocked")
    blocked_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    unblocked_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    unblock_reason = db.Column(db.Text, nullable=True)
    unblocked_at = db.Column(db.DateTime, nullable=True)
    active_document_id = db.Column(
        db.Integer,
        db.Computed(
            "CASE WHEN status = 'blocked' THEN document_id ELSE NULL END",
            persisted=True,
        ),
        nullable=True,
    )

    document = db.relationship("Document", foreign_keys=[document_id])
    blocked_by = db.relationship("User", foreign_keys=[blocked_by_id])
    unblocked_by = db.relationship("User", foreign_keys=[unblocked_by_id])
