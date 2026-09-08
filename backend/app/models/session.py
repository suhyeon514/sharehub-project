"""
Session 모델
- 역할: 로그인 세션
- 보안 프로젝트 연결: Session Security
- 관계: User 1 ---- N Session
"""
from app.extensions import db


class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # 세션 식별 토큰 (쿠키/헤더로 전달되는 값)
    session_token = db.Column(db.String(255), unique=True, nullable=False)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    expires_at = db.Column(db.DateTime, nullable=False)

    # Session Security 실습(세션 고정/탈취 등)을 위한 최소 메타데이터
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # 관계
    user = db.relationship("User", back_populates="sessions")

    def __repr__(self):
        return f"<Session user_id={self.user_id} active={self.is_active}>"
