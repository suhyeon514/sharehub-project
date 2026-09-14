from flask import Blueprint, jsonify
from app.services.document_permissions import document_view_condition
from app.services.document_blocks import document_not_blocked_condition

from app.extensions import db
from app.models import Document, DocumentShare
from app.routes.auth import login_required
from app.routes.documents import serialize_document_summary


dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/api/dashboard",
)


@dashboard_bp.route("", methods=["GET"])
@login_required
def get_dashboard(current_user, current_session):
    # 1. 내가 등록한 자료
    my_documents_count = Document.query.filter(
        Document.owner_id == current_user.id,
        document_not_blocked_condition(Document.id),
    ).count()

    # 2. 나에게 명시적으로 공유된 자료
    shared_documents_count = (
        db.session.query(DocumentShare.document_id)
        .join(
            Document,
            Document.id == DocumentShare.document_id,
        )
        .filter(
            DocumentShare.shared_with_id == current_user.id,
            Document.owner_id != current_user.id,
            document_not_blocked_condition(Document.id),
        )
        .distinct()
        .count()
    )

    # 3. 같은 부서의 팀 공개 자료
    if current_user.department_id is not None:
        team_documents_count = Document.query.filter(
            Document.visibility == "team",
            Document.department_id == current_user.department_id,
            Document.owner_id != current_user.id,
            document_not_blocked_condition(Document.id),
        ).count()
    else:
        team_documents_count = 0

    # 4. 현재 사용자가 접근 가능한 최근 자료
    recent_documents = (
        Document.query
        .filter(document_view_condition(current_user))
        .order_by(
            Document.updated_at.desc(),
            Document.id.desc(),
        )
        .limit(5)
        .all()
    )

    return jsonify(
        {
            "data": {
                "my_documents": my_documents_count,
                "shared_documents": shared_documents_count,
                "team_documents": team_documents_count,
                "recent_documents": [
                    serialize_document_summary(document)
                    for document in recent_documents
                ],
            }
        }
    ), 200
