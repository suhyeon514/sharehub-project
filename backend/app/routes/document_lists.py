from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Document, DocumentShare, User
from app.routes.auth import login_required
from app.services.document_permissions import document_view_condition


document_lists_bp = Blueprint("document_lists", __name__, url_prefix="/api/documents")


@document_lists_bp.get("/shared")
@login_required
def shared_documents(current_user, current_session):
    query = request.args.get("q", "").strip()
    sharer = request.args.get("sharer", "").strip()
    permission = request.args.get("permission", "")
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "10"))
    except ValueError:
        return jsonify({"message": "페이지는 정수로 입력해주세요."}), 400
    if page < 1 or per_page < 1 or per_page > 100:
        return jsonify({"message": "페이지는 1 이상, 페이지 크기는 1~100이어야 합니다."}), 400
    if len(query) > 255 or len(sharer) > 50 or permission not in ("", "view", "download", "edit"):
        return jsonify({"message": "검색 조건을 확인해주세요."}), 400

    statement = (
        db.select(DocumentShare).join(Document)
        .where(DocumentShare.shared_with_id == current_user.id, document_view_condition(current_user))
    )
    if query:
        statement = statement.where(Document.title.contains(query, autoescape=True))
    if sharer:
        statement = statement.where(DocumentShare.shared_by.has(User.username.contains(sharer, autoescape=True)))
    if permission:
        statement = statement.where(DocumentShare.permission == permission)
    total = db.session.scalar(db.select(db.func.count()).select_from(statement.subquery()))
    shares = db.session.execute(
        statement.options(joinedload(DocumentShare.document), joinedload(DocumentShare.shared_by))
        .order_by(DocumentShare.created_at.desc(), DocumentShare.id.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()
    return jsonify({
        "items": [{
            "share_id": share.id,
            "document": {"id": share.document.id, "title": share.document.title},
            "shared_by": {"id": share.shared_by.id, "username": share.shared_by.username},
            "permission": share.permission,
            "shared_at": share.created_at.isoformat() if share.created_at else None,
        } for share in shares],
        "pagination": {
            "page": page, "per_page": per_page, "total": total,
            "pages": (total + per_page - 1) // per_page,
        },
    })


@document_lists_bp.get("/team")
@login_required
def team_documents(current_user, current_session):
    query = request.args.get("q", "").strip()
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "10"))
    except ValueError:
        return jsonify({"message": "페이지는 정수로 입력해주세요."}), 400
    if page < 1 or not 1 <= per_page <= 100 or len(query) > 255:
        return jsonify({"message": "검색어는 255자 이내, 페이지는 1 이상, 페이지 크기는 1~100이어야 합니다."}), 400

    # 부서 필터를 클라이언트에서 받지 않는다. 관리자도 본인 부서 기준이다.
    department = current_user.department
    statement = db.select(Document).where(
        Document.visibility == "team",
        Document.department_id.isnot(None),
        Document.department_id == current_user.department_id,
        document_view_condition(current_user),
    )
    if query:
        statement = statement.where(Document.title.contains(query, autoescape=True))
    total = db.session.scalar(db.select(db.func.count()).select_from(statement.subquery()))
    documents = db.session.execute(
        statement.options(joinedload(Document.owner))
        .order_by(Document.updated_at.desc(), Document.id.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()
    return jsonify({
        "department": {"id": department.id, "name": department.name} if department else None,
        "items": [{
            "id": document.id, "title": document.title,
            "owner": {"id": document.owner.id, "username": document.owner.username},
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        } for document in documents],
        "pagination": {"page": page, "per_page": per_page, "total": total,
                       "pages": (total + per_page - 1) // per_page},
    })
