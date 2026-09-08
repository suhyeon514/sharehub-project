"""
User 모델
- 역할: 사용자/역할
- 보안 프로젝트 연결: 인증·RBAC
- 관계: Department 1 ---- N User
        User 1 ---- N Session / Document / Comment / ActivityLog
        User 1 ---- N DocumentShare (shared_by / shared_with 양방향)
- 문서 9번(10개 페이지)의 /admin 페이지 근거로 role 컬럼 필요
"""
from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Authorization Matrix의 Admin 열 근거 (일반 사용자 vs 관리자)
    role = db.Column(db.String(20), nullable=False, default="user")  # user / admin

    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=True
    )

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # 관계
    department = db.relationship("Department", back_populates="users")

    sessions = db.relationship(
        "Session", back_populates="user", lazy=True, cascade="all, delete-orphan"
    )
    documents = db.relationship(
        "Document", back_populates="owner", lazy=True
    )
    comments = db.relationship(
        "Comment", back_populates="user", lazy=True
    )
    activity_logs = db.relationship(
        "ActivityLog", back_populates="user", lazy=True
    )

    # DocumentShare는 User를 두 번(shared_by / shared_with) 참조하므로
    # 각각의 relationship은 document_share.py 쪽에서 foreign_keys로 명시하고
    # 여기서는 back_populates만 연결한다.
    shared_documents_sent = db.relationship(
        "DocumentShare",
        foreign_keys="DocumentShare.shared_by_id",
        back_populates="shared_by",
        lazy=True,
    )
    shared_documents_received = db.relationship(
        "DocumentShare",
        foreign_keys="DocumentShare.shared_with_id",
        back_populates="shared_with",
        lazy=True,
    )

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
