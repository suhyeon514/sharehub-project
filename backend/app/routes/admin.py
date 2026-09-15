import json
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import User, Document, DocumentBlock, DocumentUnblockRequest, ActivityLog
from app.services.admin_permissions import admin_required

ACTION_LABELS = {
    "DOCUMENT_UPDATE": "문서 수정",
    "DOCUMENT_SHARE": "문서 공유",
    "DOCUMENT_BLOCK": "문서 차단",
    "DOCUMENT_UNBLOCK_REVIEW": "소명 심사",
    "DOCUMENT_DELETE": "문서 삭제",
}


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def timestamp(value):
    return value.isoformat() if value else None


def block_timestamp(value):
    # 차단 API는 UTC를 명시적으로 저장한다. 기존 수동 데이터도 UTC 기준인지 확인 필요.
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()


def block_error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


@admin_bp.post("/documents/<int:document_id>/blocks")
@admin_required
def create_document_block(document_id, current_user, current_session):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"block_reason", "block_basis"}:
        return block_error("VALIDATION_ERROR", "차단 사유와 내부 근거만 입력해주세요.", 400)
    values = {}
    for field, label, limit in (("block_reason", "차단 사유", 1000), ("block_basis", "내부 근거", 5000)):
        value = data[field]
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
            return block_error("VALIDATION_ERROR", f"{label}는 앞뒤 공백을 제외하고 1~{limit:,}자로 입력해주세요.", 400)
        values[field] = value.strip()

    try:
        document = db.session.execute(db.select(Document).where(
            Document.id == document_id,
        ).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        if document is None:
            db.session.rollback()
            return block_error("DOCUMENT_NOT_FOUND", "문서를 찾을 수 없습니다.", 404)
        # 공유 변경과 동일하게 문서부터 잠그고 최신 활성 차단을 locking read한다.
        active = db.session.execute(db.select(DocumentBlock.id).where(
            DocumentBlock.document_id == document_id,
            DocumentBlock.status == "blocked",
        ).with_for_update()).scalar_one_or_none()
        if active is not None:
            db.session.rollback()
            return block_error("DOCUMENT_ALREADY_BLOCKED", "이미 차단된 문서입니다.", 409)
        block = DocumentBlock(
            document_id=document_id, document_id_snapshot=document_id,
            blocked_by_id=current_user.id, status="blocked",
            blocked_at=datetime.now(timezone.utc).replace(tzinfo=None), **values,
        )
        db.session.add(block)
        db.session.flush()
        result = {
            "id": block.id, "document_id": document_id, "status": block.status,
            **values, "blocked_at": block_timestamp(block.blocked_at),
        }
        db.session.add(ActivityLog(
            user_id=current_user.id, action_type="DOCUMENT_BLOCK",
            ip_address=request.remote_addr,
            detail=json.dumps({"operation": "block", "document_id": document_id,
                "block_id": block.id, "block_reason": block.block_reason}),
        ))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return jsonify({"block": result}), 201


def safe_detail(value, action_type=None):
    # 자유 형식 원문은 인증 정보/파일 경로를 포함할 수 있어 노출하지 않는다.
    try:
        detail = json.loads(value or "{}")
    except (ValueError, TypeError):
        return {}
    if not isinstance(detail, dict):
        return {}
    if action_type == "DOCUMENT_DELETE":
        result = {}
        if detail.get("operation") == "delete":
            result["operation"] = "delete"
        if type(detail.get("document_id")) is int:
            result["document_id"] = detail["document_id"]
        return result
    if action_type == "DOCUMENT_UPDATE":
        result = {}
        if detail.get("operation") == "update":
            result["operation"] = "update"
        if type(detail.get("document_id")) is int:
            result["document_id"] = detail["document_id"]
        fields = detail.get("changed_fields")
        if isinstance(fields, list):
            result["changed_fields"] = [field for field in ("title", "description") if field in fields]
        return result
    result = {}
    for key in ("document_id", "share_id", "shared_with_id", "block_id", "request_id"):
        if type(detail.get(key)) is int:
            result[key] = detail[key]
    if detail.get("operation") in ("create", "update", "delete", "block", "review"):
        result["operation"] = detail["operation"]
    if detail.get("operation") == "review":
        if detail.get("decision") in ("approved", "rejected"):
            result["decision"] = detail["decision"]
        if isinstance(detail.get("review_comment"), str):
            result["review_comment"] = detail["review_comment"]
    if detail.get("operation") == "block" and isinstance(detail.get("block_reason"), str):
        result["block_reason"] = detail["block_reason"]
    for key in ("before_permission", "after_permission"):
        if detail.get(key) in (None, "view", "download", "edit"):
            result[key] = detail.get(key)
    return result


@admin_bp.get("/<resource>")
@admin_required
def admin_list(resource, current_user, current_session):
    if resource not in ("users", "documents", "activity-logs"):
        return jsonify({"message": "목록을 찾을 수 없습니다."}), 404
    query = request.args.get("q", "").strip()
    try:
        page = int(request.args.get("page", "1"))
        size = int(request.args.get("per_page", "10"))
    except ValueError:
        return jsonify({"message": "페이지는 정수여야 합니다."}), 400
    if page < 1 or not 1 <= size <= 100 or len(query) > 255:
        return jsonify({"message": "검색어 또는 페이지 범위를 확인해주세요."}), 400
    if resource == "users":
        model, field = User, User.username
        options = [joinedload(User.department)]
    elif resource == "documents":
        model, field = Document, Document.title
        options = [joinedload(Document.owner), joinedload(Document.department)]
    else:
        model, field = ActivityLog, ActivityLog.action_type
        options = [joinedload(ActivityLog.user)]
    statement = db.select(model)
    if resource == "documents":
        status = request.args.get("status", "")
        if status not in ("", "normal", "blocked", "pending", "rejected", "cancelled"):
            return block_error("VALIDATION_ERROR", "올바른 문서 상태를 선택해주세요.", 400)
        active = db.select(DocumentBlock.id).where(
            DocumentBlock.document_id == Document.id, DocumentBlock.status == "blocked",
        )
        if status == "normal":
            statement = statement.where(~active.exists())
        elif status:
            if status != "blocked":
                latest_status = db.select(DocumentUnblockRequest.status).where(
                    DocumentUnblockRequest.block_id == DocumentBlock.id,
                ).order_by(DocumentUnblockRequest.requested_at.desc(), DocumentUnblockRequest.id.desc()
                ).limit(1).correlate(DocumentBlock).scalar_subquery()
                active = active.where(latest_status == status)
            statement = statement.where(active.exists())
    if query:
        condition = field.contains(query, autoescape=True)
        if resource == "activity-logs":
            matching_actions = [code for code, label in ACTION_LABELS.items() if query in label]
            condition = db.or_(condition, ActivityLog.action_type.in_(matching_actions))
        statement = statement.where(condition)
    total = db.session.scalar(db.select(db.func.count()).select_from(statement.subquery()))
    rows = db.session.execute(statement.options(*options).order_by(model.created_at.desc(), model.id.desc())
        .offset((page - 1) * size).limit(size)).scalars().all()
    items = []
    active_blocks = {}
    if resource == "documents" and rows:
        latest_request_status = db.select(DocumentUnblockRequest.status).where(
            DocumentUnblockRequest.block_id == DocumentBlock.id,
        ).order_by(DocumentUnblockRequest.requested_at.desc(), DocumentUnblockRequest.id.desc()
        ).limit(1).correlate(DocumentBlock).scalar_subquery()
        blocks = db.session.execute(db.select(DocumentBlock, latest_request_status).where(
            DocumentBlock.document_id.in_([row.id for row in rows]),
            DocumentBlock.status == "blocked",
        )).all()
        active_blocks = {block.document_id: {
            "id": block.id, "status": block.status, "blocked_at": block_timestamp(block.blocked_at),
            "latest_request_status": request_status,
        } for block, request_status in blocks}
    for row in rows:
        if resource == "users":
            items.append({"id": row.id, "username": row.username, "role": row.role,
                "department": row.department.name if row.department else None, "created_at": timestamp(row.created_at)})
        elif resource == "documents":
            items.append({"id": row.id, "title": row.title, "owner": row.owner.username,
                "department": row.department.name if row.department else None,
                "visibility": row.visibility, "updated_at": timestamp(row.updated_at),
                "active_block": active_blocks.get(row.id)})
        else:
            items.append({"id": row.id, "username": row.user.username if row.user else None,
                "action_type": row.action_type, "action_label": ACTION_LABELS.get(row.action_type, row.action_type), "created_at": timestamp(row.created_at), "detail": safe_detail(row.detail, row.action_type)})
    return jsonify({"items": items, "pagination": {"page": page, "per_page": size,
        "total": total, "pages": (total + size - 1) // size}})
