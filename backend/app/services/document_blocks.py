"""
문서 차단 공통 서비스

역할
- 현재 활성 차단 조회
- 단건 문서의 차단 여부 확인
- 목록/검색/대시보드에서 차단 문서를 SQL 단계에서 제외할 조건 제공
- DOCUMENT_BLOCKED 공통 응답 생성

주의
- blocked_response()는 문서에 원래 접근 근거(owner/team/share)가 있는
  사용자에게만 반환해야 한다.
- 무관한 사용자에게는 문서 존재/차단 여부를 숨기기 위해
  기존 DOCUMENT_NOT_FOUND(404) 흐름을 유지한다.
"""

from flask import jsonify
from sqlalchemy import and_, exists

from app.models import DocumentBlock


def get_active_document_block(document_id):
    """
    문서의 현재 활성 차단 1건을 반환한다.

    활성 차단이 없으면 None.
    DB의 uq_document_blocks_active_document 제약으로
    동일 문서에 활성 차단은 최대 1건만 존재한다.
    """
    return (
        DocumentBlock.query
        .filter(
            DocumentBlock.document_id == document_id,
            DocumentBlock.status == "blocked",
        )
        .first()
    )


def is_document_blocked(document_id):
    """
    현재 문서가 관리자에 의해 차단되어 있는지 반환한다.
    """
    return get_active_document_block(document_id) is not None


def document_not_blocked_condition(document_id_column):
    """
    목록/검색/대시보드 Query에서 차단 문서를 제외하기 위한
    NOT EXISTS 조건을 반환한다.

    사용 예:
        Document.query.filter(
            document_not_blocked_condition(Document.id)
        )

    문서 목록을 가져온 뒤 문서마다 is_document_blocked()를 호출하지 않는다.
    """
    active_block_exists = exists().where(
        and_(
            DocumentBlock.document_id == document_id_column,
            DocumentBlock.status == "blocked",
        )
    )

    return ~active_block_exists


def blocked_response():
    """
    원래 문서 접근 근거가 있는 사용자가 차단 문서에 접근했을 때
    사용하는 공통 응답.

    이 함수 호출 전에 반드시 owner/team/share 등의
    기본 접근 근거를 확인해야 한다.
    """
    return (
        jsonify(
            {
                "error": {
                    "code": "DOCUMENT_BLOCKED",
                    "message": "관리자에 의해 이용이 제한된 문서입니다.",
                }
            }
        ),
        403,
    )
