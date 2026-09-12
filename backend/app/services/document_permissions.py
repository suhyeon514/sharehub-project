"""확정 공유 정책에 따른 문서 권한 검사."""

from app.models import DocumentShare


def can_manage_shares(user, document):
    """공유 관리는 소유자만 허용한다. edit 공유는 포함하지 않는다."""
    return document.owner_id == user.id


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



PERMISSION_LEVELS = {
    "view": 1,
    "download": 2,
    "edit": 3,
}


def get_document_access(document, current_user):
    # 1. 소유자는 모든 기본 문서 작업 허용
    if document.owner_id == current_user.id:
        return {
            "allowed": True,
            "source": "owner",
            "permission": "edit",
        }

    # 2. 같은 부서의 team 문서는 기본 view 허용
    if (
        document.visibility == "team"
        and document.department_id is not None
        and current_user.department_id == document.department_id
    ):
        team_access = {
            "allowed": True,
            "source": "team",
            "permission": "view",
        }
    else:
        team_access = None

    # 3. 개별 공유 확인
    share = DocumentShare.query.filter_by(
        document_id=document.id,
        shared_with_id=current_user.id,
    ).first()

    if share is not None:
        share_permission = share.permission if share.permission in PERMISSION_LEVELS else "view"

        if share_permission in PERMISSION_LEVELS:
            if team_access is None:
                return {
                    "allowed": True,
                    "source": "share",
                    "permission": share_permission,
                    "share": share,
                }

            # 팀 기본 view보다 개별 공유 권한이 높으면 개별 공유 우선
            if (
                PERMISSION_LEVELS[share_permission]
                > PERMISSION_LEVELS[team_access["permission"]]
            ):
                return {
                    "allowed": True,
                    "source": "share",
                    "permission": share_permission,
                    "share": share,
                }

    if team_access is not None:
        return team_access

    return {
        "allowed": False,
        "source": None,
        "permission": None,
    }


def has_document_permission(access, required_permission):
    if not access["allowed"]:
        return False

    current_level = PERMISSION_LEVELS.get(access["permission"], 0)
    if required_permission not in PERMISSION_LEVELS:
        return False
    required_level = PERMISSION_LEVELS[required_permission]

    return current_level >= required_level


def can_view_document(user, document):
    return has_document_permission(get_document_access(document, user), "view")


def can_download_document(user, document):
    return has_document_permission(get_document_access(document, user), "download")


def can_edit_document(user, document):
    return has_document_permission(get_document_access(document, user), "edit")
