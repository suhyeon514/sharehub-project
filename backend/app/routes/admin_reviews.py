import json
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models import ActivityLog, Document, DocumentBlock, DocumentUnblockRequest
from app.services.admin_permissions import admin_required
from app.services.unblock_reviews import MESSAGES, query_requests, review_reason, serialize

admin_reviews_bp = Blueprint("admin_reviews", __name__, url_prefix="/api/admin/unblock-requests")


def error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def missing():
    return error("UNBLOCK_REQUEST_NOT_FOUND", "소명 요청을 찾을 수 없습니다.", 404)


@admin_reviews_bp.get("")
@admin_required
def list_requests(current_user, current_session):
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    try:
        page = int(request.args.get("page", "1"))
        size = int(request.args.get("per_page", "10"))
        block_id = int(request.args["block_id"]) if "block_id" in request.args else None
        if page < 1 or not 1 <= size <= 100 or (block_id is not None and block_id < 1):
            raise ValueError
    except ValueError:
        return error("VALIDATION_ERROR", "페이지 또는 차단 ID를 확인해주세요.", 400)
    if status not in ("", "pending", "approved", "rejected", "cancelled") or len(q) > 255:
        return error("VALIDATION_ERROR", "상태 또는 검색어를 확인해주세요.", 400)
    # 삭제된 문서 이력의 조회 계약은 후속 범위이다.
    statement = query_requests().join(DocumentUnblockRequest.block).join(DocumentBlock.document)
    if status:
        statement = statement.where(DocumentUnblockRequest.status == status)
    if block_id is not None:
        statement = statement.where(DocumentUnblockRequest.block_id == block_id)
    if q:
        statement = statement.where(Document.title.contains(q, autoescape=True))
    total = db.session.scalar(db.select(db.func.count()).select_from(statement.subquery()))
    rows = db.session.execute(statement.order_by(DocumentUnblockRequest.requested_at.desc(),
        DocumentUnblockRequest.id.desc()).offset((page - 1) * size).limit(size)).scalars().all()
    return jsonify({"items": [serialize(row, current_user) for row in rows],
        "pagination": {"page": page, "per_page": size, "total": total, "pages": (total + size - 1) // size}})


@admin_reviews_bp.get("/<int:request_id>")
@admin_required
def request_detail(request_id, current_user, current_session):
    appeal = db.session.execute(query_requests().where(DocumentUnblockRequest.id == request_id)).scalar_one_or_none()
    if appeal is None or appeal.block.document is None:
        return missing()
    return jsonify(serialize(appeal, current_user, detail=True))


@admin_reviews_bp.post("/<int:request_id>/review")
@admin_required
def review(request_id, current_user, current_session):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"decision", "review_comment"}:
        return error("VALIDATION_ERROR", "결정과 심사 의견만 입력해주세요.", 400)
    decision, comment = data["decision"], data["review_comment"]
    if decision not in ("approved", "rejected") or not isinstance(comment, str) or not 1 <= len(comment.strip()) <= 1000:
        return error("VALIDATION_ERROR", "승인·거절을 선택하고 심사 의견을 1~1,000자로 입력해주세요.", 400)
    try:
        link = db.session.execute(db.select(DocumentUnblockRequest.block_id, DocumentBlock.document_id)
            .join(DocumentBlock, DocumentUnblockRequest.block_id == DocumentBlock.id)
            .where(DocumentUnblockRequest.id == request_id)).one_or_none()
        if link is None:
            db.session.rollback()
            return missing()
        document = db.session.execute(db.select(Document).where(Document.id == link.document_id)
            .with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        block = db.session.execute(db.select(DocumentBlock).where(DocumentBlock.id == link.block_id)
            .with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        appeal = db.session.execute(db.select(DocumentUnblockRequest).where(DocumentUnblockRequest.id == request_id)
            .with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        if appeal is None or block is None:
            db.session.rollback()
            return missing()
        if appeal.block_id != block.id or block.document_id != link.document_id:
            db.session.rollback()
            return error("DOCUMENT_BLOCK_NOT_ACTIVE", MESSAGES["DOCUMENT_BLOCK_NOT_ACTIVE"], 409)
        reason = review_reason(appeal, block, document, current_user)
        if reason:
            db.session.rollback()
            return error(reason, MESSAGES[reason], 403 if reason == "SELF_REVIEW_NOT_ALLOWED" else 409)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        appeal.status = decision
        appeal.review_comment = comment.strip()
        appeal.reviewed_by = current_user
        appeal.reviewed_at = now
        if decision == "approved":
            block.status = "unblocked"
            block.unblocked_by_id = current_user.id
            block.unblock_reason = comment.strip()
            block.unblocked_at = now
        db.session.add(ActivityLog(user_id=current_user.id, action_type="DOCUMENT_UNBLOCK_REVIEW",
            ip_address=request.remote_addr, detail=json.dumps({"operation": "review", "document_id": document.id,
                "block_id": block.id, "request_id": appeal.id, "decision": decision, "review_comment": comment.strip()})))
        db.session.flush()
        result = serialize(appeal, current_user, detail=True, block=block, document=document)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return jsonify(result)
