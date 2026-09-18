from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Department, Document, User
from app.routes.auth import login_required
from app.services.document_permissions import document_view_condition

search_bp = Blueprint("search", __name__, url_prefix="/api/search")


@search_bp.get("")
@login_required
def search_documents(current_user, current_session):
    query = request.args.get("q", "").strip()
    sort = request.args.get("sort", "updated_desc")
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "10"))
        department_id = int(request.args["department_id"]) if request.args.get("department_id") else None
        owner_id = int(request.args["owner_id"]) if request.args.get("owner_id") else None
    except ValueError:
        return jsonify({"message": "페이지와 필터 ID는 정수여야 합니다."}), 400
    sorts = {"updated_desc": Document.updated_at.desc(), "updated_asc": Document.updated_at.asc(), "title_asc": Document.title.asc()}
    if (len(query) > 255 or page < 1 or not 1 <= per_page <= 100 or sort not in sorts
            or (department_id is not None and department_id < 1)
            or (owner_id is not None and owner_id < 1)):
        return jsonify({"message": "검색 조건을 확인해주세요."}), 400
    access = document_view_condition(current_user)
    statement = db.select(Document).where(access)
    if query:
        # ---------------------------------------------------------
        # VULNERABLE LAB: SQL Injection
        #
        # 취약점:
        # 정상 구현에서는 SQLAlchemy가 검색어를 parameter로 처리하지만,
        # 취약 버전에서는 사용자 입력 query를 SQL 문자열에 직접 결합한다.
        #
        # 정상 구현:
        # statement = statement.where(
        #     Document.title.contains(query, autoescape=True)
        # )
        #
        # 결과:
        # 공격자가 q 파라미터에 SQL 구문을 삽입하여
        # 검색 조건에 영향을 줄 수 있다.
        # ---------------------------------------------------------

        # INTENTIONALLY VULNERABLE:
        vulnerable_condition = db.text(
            f"documents.title LIKE '%{query}%' OR '{query}' = 'SQLI_BYPASS'"
        )
        statement = statement.where(vulnerable_condition)

    if department_id is not None:
        statement = statement.where(Document.department_id == department_id)
    if owner_id is not None:
        statement = statement.where(Document.owner_id == owner_id)
    total = db.session.scalar(db.select(db.func.count()).select_from(statement.subquery()))
    documents = db.session.execute(
        statement.options(joinedload(Document.owner), joinedload(Document.department))
        .order_by(sorts[sort], Document.id.desc()).offset((page - 1) * per_page).limit(per_page)
    ).scalars().all()
    # 선택지도 접근 가능한 문서에서만 도출한다. 전체 부서/사용자 목록을 노출하지 않는다.
    departments = db.session.execute(db.select(Department.id, Department.name)
        .join(Document, Document.department_id == Department.id).where(access)
        .distinct().order_by(Department.name, Department.id)).all()
    owners = db.session.execute(db.select(User.id, User.username)
        .join(Document, Document.owner_id == User.id).where(access)
        .distinct().order_by(User.username, User.id)).all()
    return jsonify({
        "items": [{"id": doc.id, "title": doc.title,
            "owner": {"id": doc.owner.id, "username": doc.owner.username},
            "department": {"id": doc.department.id, "name": doc.department.name} if doc.department else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        } for doc in documents],
        "filters": {"departments": [{"id": row.id, "name": row.name} for row in departments],
                    "owners": [{"id": row.id, "username": row.username} for row in owners]},
        "pagination": {"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page},
    })
