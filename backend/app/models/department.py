"""
Department 모델
- 역할: 부서
- 보안 프로젝트 연결: TEAM 접근통제
- 관계: Department 1 ---- N User
        Department 1 ---- N Document
"""
from app.extensions import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)

    # 부서명 (예: 개발팀, 인사팀) - 중복 불가
    name = db.Column(db.String(100), unique=True, nullable=False)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # 관계 (Department ├────< User / Document)
    users = db.relationship(
        "User", back_populates="department", lazy=True
    )
    documents = db.relationship(
        "Document", back_populates="department", lazy=True
    )

    def __repr__(self):
        return f"<Department {self.name}>"
