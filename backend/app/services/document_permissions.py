"""확정 공유 정책에 따른 문서 권한 검사."""


def can_manage_shares(user, document):
    """공유 관리는 소유자와 관리자만 허용한다. edit 공유는 포함하지 않는다."""
    return user.role == "admin" or document.owner_id == user.id


def document_view_condition(user):
    """일반 문서 조회용 SQL 조건. 관리자 메타데이터 관리 권한과 구분한다."""
    from sqlalchemy import and_, or_
    from app.models import Document, DocumentShare

    return or_(
        Document.owner_id == user.id,
        and_(
            Document.visibility == "team",
            Document.department_id.isnot(None),
            Document.department_id == user.department_id,
        ),
        Document.shares.any(DocumentShare.shared_with_id == user.id),
    )


def can_view_document(user, document):
    """현재 DB의 동일 조회 조건을 사용하여 개별 문서 접근을 확인한다."""
    from app.extensions import db
    from app.models import Document

    return db.session.execute(
        db.select(Document.id).where(
            Document.id == document.id, document_view_condition(user),
        )
    ).scalar_one_or_none() is not None
