import json
from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import User, Document, ActivityLog
from app.services.admin_permissions import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def timestamp(value):
    return value.isoformat() if value else None


def safe_detail(value):
    # 자유 형식 원문은 인증 정보/파일 경로를 포함할 수 있어 노출하지 않는다.
    try:
        detail = json.loads(value or "{}")
    except (ValueError, TypeError):
        return {}
    if not isinstance(detail, dict):
        return {}
    result = {}
    for key in ("document_id", "share_id", "shared_with_id"):
        if type(detail.get(key)) is int:
            result[key] = detail[key]
    if detail.get("operation") in ("create", "update", "delete"):
        result["operation"] = detail["operation"]
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
    if query:
        statement = statement.where(field.contains(query, autoescape=True))
    total = db.session.scalar(db.select(db.func.count()).select_from(statement.subquery()))
    rows = db.session.execute(statement.options(*options).order_by(model.created_at.desc(), model.id.desc())
        .offset((page - 1) * size).limit(size)).scalars().all()
    items = []
    for row in rows:
        if resource == "users":
            items.append({"id": row.id, "username": row.username, "role": row.role,
                "department": row.department.name if row.department else None, "created_at": timestamp(row.created_at)})
        elif resource == "documents":
            items.append({"id": row.id, "title": row.title, "owner": row.owner.username,
                "department": row.department.name if row.department else None,
                "visibility": row.visibility, "updated_at": timestamp(row.updated_at)})
        else:
            items.append({"id": row.id, "username": row.user.username if row.user else None,
                "action_type": row.action_type, "created_at": timestamp(row.created_at), "detail": safe_detail(row.detail)})
    return jsonify({"items": items, "pagination": {"page": page, "per_page": size,
        "total": total, "pages": (total + size - 1) // size}})
