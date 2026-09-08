"""
ActivityLog 모델
- 역할: 감사/보안 이벤트
- 보안 프로젝트 연결: Wazuh / 포렌식
- 관계: User 1 ---- N ActivityLog
- 문서 19번: ActivityLog(DB, 서비스 내부 감사용)는
  Security Log(파일, Wazuh 탐지용)와 목적이 다르지만
  request_id를 공유해 Nginx-Flask-ActivityLog 요청 추적을 가능하게 한다.
- action_type 값은 문서 19번에 명시된 이벤트 목록을 그대로 사용:
  LOGIN_SUCCESS, LOGIN_FAILURE, DOCUMENT_VIEW, DOCUMENT_DOWNLOAD,
  AUTHORIZATION_DENIED, DOCUMENT_UPLOAD, DOCUMENT_SHARE,
  COMMENT_CREATED, ADMIN_ACTION
"""
from app.extensions import db


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # 문서 19번에 명시된 이벤트 목록 (문자열 저장, 필요 시 Enum으로 전환 가능)
    action_type = db.Column(db.String(50), nullable=False)

    # Nginx -> Flask -> ActivityLog 로 이어지는 요청 추적용 (문서 19번)
    request_id = db.Column(db.String(64), nullable=True, index=True)

    # 이벤트 관련 부가 정보 (예: document_id, 실패 사유 등)
    detail = db.Column(db.Text, nullable=True)

    ip_address = db.Column(db.String(45), nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # 관계
    user = db.relationship("User", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog {self.action_type} user_id={self.user_id}>"
