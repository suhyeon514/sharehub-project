"""확정 공유 정책에 따른 문서 권한 검사."""

from sqlalchemy import and_, or_

from app.models import Document, DocumentShare
from app.services.document_blocks import (
    document_not_blocked_condition,
    is_document_blocked,
)


PERMISSION_LEVELS = {
    "view": 1,
    "download": 2,
    "edit": 3,
}


def can_manage_shares(user, document):
    """
    공유 관리는 소유자만 허용한다.
    edit 공유 사용자는 공유 관리 권한을 갖지 않는다.
    차단된 문서는 소유자도 공유 관리할 수 없다.
    """
    if document.owner_id != user.id:
        return False

    if is_document_blocked(document.id):
        return False

    return True


def document_view_condition(user):
    """
    일반 문서 목록 조회용 SQL 조건.

    owner / team / 개별 공유 접근 조건을 만족하면서
    현재 차단되지 않은 문서만 조회한다.

    관리자 메타데이터 관리 권한과는 별도로 사용한다.
    """
    access_condition = or_(
        Document.owner_id == user.id,
        and_(
            Document.visibility == "team",
            Document.department_id.isnot(None),
            Document.department_id == user.department_id,
        ),
        Document.shares.any(
            DocumentShare.shared_with_id == user.id
        ),
    )

    return and_(
        access_condition,
        document_not_blocked_condition(Document.id),
    )


def get_document_access(document, current_user):
    """
    차단 여부와 관계없이 사용자의 원래 문서 접근 근거를 계산한다.

    이 함수에서는 차단 여부를 검사하지 않는다.
    그래야 라우트에서
    - 접근 근거 없음 → 404
    - 접근 근거 있음 + 차단 → 403 DOCUMENT_BLOCKED
    를 구분할 수 있다.
    """

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
        share_permission = (
            share.permission
            if share.permission in PERMISSION_LEVELS
            else "view"
        )

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

    if required_permission not in PERMISSION_LEVELS:
        return False

    current_level = PERMISSION_LEVELS.get(
        access["permission"],
        0,
    )
    required_level = PERMISSION_LEVELS[required_permission]

    return current_level >= required_level


def can_view_document(user, document):
    access = get_document_access(document, user)

    if not access["allowed"]:
        return False

    if is_document_blocked(document.id):
        return False

    return has_document_permission(access, "view")


def can_download_document(user, document):
    access = get_document_access(document, user)

    if not access["allowed"]:
        return False

    if is_document_blocked(document.id):
        return False

    return has_document_permission(access, "download")


def can_edit_document(user, document):
    access = get_document_access(document, user)

    if not access["allowed"]:
        return False

    if is_document_blocked(document.id):
        return False

    return has_document_permission(access, "edit")