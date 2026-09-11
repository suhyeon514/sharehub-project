"""
Document 모델
- 역할: 파일/메타데이터
- 보안 프로젝트 연결: IDOR / File Upload
- 문서 8번 "Document가 핵심 Domain" 근거로 아래 속성 확정
    owner / department / visibility / actual file / comments / sharing
- 관계: Department 1 ---- N Document
        User(owner) 1 ---- N Document
        Document 1 ---- N Comment / DocumentShare
"""
from app.extensions import db


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(255), nullable=False)

    description = db.Column(db.Text, nullable=True)

    # owner (문서 8번 attribute)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # department (문서 8번 attribute, /documents/team 페이지 근거)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=True
    )

    # 기본 공개 범위
    # private: 기본적으로 소유자만 접근
    # team: 같은 부서 사용자 접근
    # 특정 사용자 공유는 document_shares에서 별도로 처리
    visibility = db.Column(db.String(20), nullable=False, default="private")

    # actual file (문서 8번 attribute) - 실제 파일은 디스크/스토리지에 두고 경로만 저장
    file_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(
        db.DateTime, server_default=db.func.now(), onupdate=db.func.now()
    )

    # 관계
    owner = db.relationship("User", back_populates="documents")
    department = db.relationship("Department", back_populates="documents")

    comments = db.relationship(
        "Comment", back_populates="document", lazy=True, cascade="all, delete-orphan"
    )
    shares = db.relationship(
        "DocumentShare",
        back_populates="document",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Document {self.title} owner_id={self.owner_id}>"
