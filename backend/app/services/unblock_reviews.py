"""관리자 소명 조회와 심사의 공통 판정·직렬화."""
from datetime import timezone
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import Document, DocumentBlock, DocumentUnblockRequest

MESSAGES = {
    "SELF_REVIEW_NOT_ALLOWED": "본인 문서 또는 본인 요청은 심사할 수 없습니다.",
    "UNBLOCK_REQUEST_NOT_PENDING": "이미 처리되었거나 취소된 요청입니다.",
    "DOCUMENT_BLOCK_NOT_ACTIVE": "현재 활성 차단에 대한 요청이 아닙니다.",
}


def review_reason(appeal, block, document, user):
    if appeal.requester_id == user.id or (document and document.owner_id == user.id):
        return "SELF_REVIEW_NOT_ALLOWED"
    if appeal.status != "pending":
        return "UNBLOCK_REQUEST_NOT_PENDING"
    if document is None or block.document_id != document.id or block.status != "blocked":
        return "DOCUMENT_BLOCK_NOT_ACTIVE"
    return None


def timestamp(value):
    # 기존 인증·차단 API와 동일한 UTC 저장 규약. 수동 입력 이력의 시간대는 별도 확인.
    if value is None:
        return None
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()


def person(user):
    return {"id": user.id, "username": user.username} if user else None


def query_requests():
    return db.select(DocumentUnblockRequest).options(
        joinedload(DocumentUnblockRequest.requester),
        joinedload(DocumentUnblockRequest.reviewed_by),
        joinedload(DocumentUnblockRequest.block).joinedload(DocumentBlock.document),
    )


def serialize(appeal, user, *, detail=False, block=None, document=None):
    block = block if block is not None else appeal.block
    document = document if document is not None else block.document
    reason = review_reason(appeal, block, document, user)
    flags = {"can_review": reason is None, "review_unavailable_reason": reason}
    request_data = {"id": appeal.id, "status": appeal.status,
        "requested_at": timestamp(appeal.requested_at), "requester": person(appeal.requester)}
    if not detail:
        return {**request_data, "document_id": document.id if document else block.document_id_snapshot,
            "title": document.title if document else None, "block_id": block.id,
            "block_status": block.status, **flags}
    return {"document": {"id": document.id, "title": document.title} if document else None,
        "block": {"id": block.id, "status": block.status, "block_reason": block.block_reason,
            "block_basis": block.block_basis, "blocked_at": timestamp(block.blocked_at),
            "is_current_block": document is not None and block.status == "blocked" and block.document_id == document.id},
        "unblock_request": {**request_data, "request_reason": appeal.request_reason,
            "review_comment": appeal.review_comment, "reviewed_by": person(appeal.reviewed_by),
            "reviewed_at": timestamp(appeal.reviewed_at), "cancelled_at": timestamp(appeal.cancelled_at)}, **flags}
