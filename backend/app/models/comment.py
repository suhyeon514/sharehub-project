"""
Comment 모델
- 역할: 댓글
- 보안 프로젝트 연결: Stored XSS
- 관계: User 1 ---- N Comment
        Document 1 ---- N Comment
"""
from app.extensions import db


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)

    document_id = db.Column(
        db.Integer, db.ForeignKey("documents.id"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Stored XSS 실습 대상이 되는 사용자 입력 필드
    content = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # 관계
    document = db.relationship("Document", back_populates="comments")
    user = db.relationship("User", back_populates="comments")

    def __repr__(self):
        return f"<Comment document_id={self.document_id} user_id={self.user_id}>"
