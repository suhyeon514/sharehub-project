"""
DocumentShare 모델
- 역할: 사용자 간 공유
- 보안 프로젝트 연결: IDOR / Authorization
- ERD 근거: User ├────< DocumentShare (shared_by)
            User ├────< DocumentShare (shared_with)
  → User를 두 번 참조하는 구조이므로 foreign_keys를 명시해야 함
- permission 컬럼: Authorization Matrix의
  "Shared VIEW / Shared DOWNLOAD / Shared EDIT" 구분 근거
"""
from app.extensions import db


class DocumentShare(db.Model):
    __tablename__ = "document_shares"

    __table_args__ = (
        db.UniqueConstraint(
            "document_id",
            "shared_with_id",
            name="uq_document_share_target",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id"), nullable=False
    )

    # 공유한 사람 (Owner 관점)
    shared_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    # 공유받은 사람
    shared_with_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )

    # Authorization Matrix 기준: view / download / edit
    permission = db.Column(db.String(20), nullable=False, default="view")

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # 관계
    document = db.relationship("Document", back_populates="shares")

    shared_by = db.relationship(
        "User", foreign_keys=[shared_by_id], back_populates="shared_documents_sent"
    )
    shared_with = db.relationship(
        "User",
        foreign_keys=[shared_with_id],
        back_populates="shared_documents_received",
    )

    def __repr__(self):
        return (
            f"<DocumentShare document_id={self.document_id} "
            f"{self.shared_by_id}->{self.shared_with_id} ({self.permission})>"
        )
