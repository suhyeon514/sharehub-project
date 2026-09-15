"""
모델을 한 곳에서 import 해서, Flask-Migrate가
`flask db migrate` 실행 시 전체 모델을 인식하도록 한다.

문서 STEP 7의 FK 관계 순서를 그대로 따른다:
Department -> User -> Session
Department/User -> Document
User/Document -> Comment
User/Document -> DocumentShare
User -> ActivityLog
"""
from app.models.department import Department
from app.models.user import User
from app.models.session import Session
from app.models.document import Document
from app.models.comment import Comment
from app.models.document_share import DocumentShare
from app.models.activity_log import ActivityLog
from app.models.document_block import DocumentBlock
from app.models.document_unblock_request import DocumentUnblockRequest
from app.models.file_cleanup_job import FileCleanupJob

__all__ = [
    "Department",
    "User",
    "Session",
    "Document",
    "Comment",
    "DocumentShare",
    "ActivityLog",
    "DocumentBlock",
    "DocumentUnblockRequest",
    "FileCleanupJob",
]
