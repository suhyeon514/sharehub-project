"""
FileCleanupJob 모델

문서 DB 삭제가 완료된 이후 실제 업로드 파일을 정리하기 위한
영구 cleanup 작업을 저장한다.

- Document와 FK를 연결하지 않는다.
- document_id_snapshot은 삭제된 문서의 식별값만 보존한다.
- file_path는 서버 내부 cleanup 처리에서만 사용한다.
- attempt_count는 현재 cleanup 사이클에서 시작된 시도 횟수다.
"""

from app.extensions import db


class FileCleanupJob(db.Model):
    __tablename__ = "file_cleanup_jobs"

    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    id = db.Column(db.Integer, primary_key=True)

    # 삭제된 Document와 FK를 맺지 않는다.
    document_id_snapshot = db.Column(
        db.Integer,
        nullable=False,
        index=True,
    )

    # 일반 API/감사 로그/CLI 출력에 노출하지 않는 서버 내부 경로.
    # 기존 documents.file_path와 동일한 길이를 사용한다.
    file_path = db.Column(
        db.String(500),
        nullable=False,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default=STATUS_PENDING,
        server_default=STATUS_PENDING,
    )

    # 현재 retry cycle에서 cleanup 처리를 시작한 횟수.
    attempt_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # 실제 경로나 원문 exception이 아닌 안전한 내부 오류 코드만 저장한다.
    last_error = db.Column(
        db.String(100),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now(),
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_file_cleanup_jobs_status",
        ),
        db.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= 5",
            name="ck_file_cleanup_jobs_attempt_count",
        ),
    )

    def __repr__(self):
        return (
            f"<FileCleanupJob id={self.id} "
            f"document_id_snapshot={self.document_id_snapshot} "
            f"status={self.status}>"
        )
