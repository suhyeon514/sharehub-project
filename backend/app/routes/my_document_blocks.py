from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.document import Document
from app.models.document_block import DocumentBlock
from app.models.document_unblock_request import DocumentUnblockRequest
from app.routes.auth import login_required



my_document_blocks_bp = Blueprint(
    "my_document_blocks",
    __name__,
    url_prefix="/api/my",
)

document_block_requests_bp = Blueprint(
    "document_block_requests",
    __name__,
    url_prefix="/api/document-blocks",
)


def to_iso(value):
    if value is None:
        return None

    return value.isoformat()


def get_latest_unblock_request(block_id):
    return (
        DocumentUnblockRequest.query
        .filter(
            DocumentUnblockRequest.block_id == block_id,
        )
        .order_by(
            DocumentUnblockRequest.requested_at.desc(),
            DocumentUnblockRequest.id.desc(),
        )
        .first()
    )


def serialize_unblock_request(unblock_request):
    if unblock_request is None:
        return None

    return {
        "id": unblock_request.id,
        "status": unblock_request.status,
        "requested_at": to_iso(
            unblock_request.requested_at,
        ),
        "review_comment": unblock_request.review_comment,
    }


def serialize_block(block, document):
    latest_request = get_latest_unblock_request(
        block.id,
    )

    return {
        # 해제된 과거 이력에서도 문서 ID를 유지하기 위해 snapshot 사용
        "document_id": block.document_id_snapshot,
        "block_id": block.id,
        "title": document.title,
        "status": block.status,
        "block_reason": block.block_reason,
        "blocked_at": to_iso(
            block.blocked_at,
        ),
        "unblock_request": serialize_unblock_request(
            latest_request,
        ),
    }


@my_document_blocks_bp.route(
    "/blocked-documents",
    methods=["GET"],
)
@login_required
def get_my_blocked_documents(
    current_user,
    current_session,
):
    rows = (
        db.session.query(
            DocumentBlock,
            Document,
        )
        .join(
            Document,
            Document.id == DocumentBlock.document_id,
        )
        .filter(
            Document.owner_id == current_user.id,
            DocumentBlock.status == "blocked",
        )
        .order_by(
            DocumentBlock.blocked_at.desc(),
            DocumentBlock.id.desc(),
        )
        .all()
    )

    return jsonify(
        {
            "data": [
                serialize_block(
                    block,
                    document,
                )
                for block, document in rows
            ]
        }
    ), 200


@my_document_blocks_bp.route(
    "/document-blocks/<int:block_id>",
    methods=["GET"],
)
@login_required
def get_my_document_block_detail(
    block_id,
    current_user,
    current_session,
):
    row = (
        db.session.query(
            DocumentBlock,
            Document,
        )
        .join(
            Document,
            Document.id == DocumentBlock.document_id,
        )
        .filter(
            DocumentBlock.id == block_id,
            Document.owner_id == current_user.id,
        )
        .first()
    )

    if row is None:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_BLOCK_NOT_FOUND",
                    "message": "차단 이력을 찾을 수 없습니다.",
                }
            }
        ), 404

    block, document = row

    return jsonify(
        {
            "data": serialize_block(
                block,
                document,
            )
        }
    ), 200

@document_block_requests_bp.route(
    "/<int:block_id>/unblock-requests",
    methods=["POST"],
)

@login_required
def create_unblock_request(
    block_id,
    current_user,
    current_session,
):
    block = db.session.get(
        DocumentBlock,
        block_id,
    )

    if block is None:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_BLOCK_NOT_FOUND",
                    "message": "차단 이력을 찾을 수 없습니다.",
                }
            }
        ), 404

    document = db.session.get(
        Document,
        block.document_id,
    )

    if (
        document is None
        or document.owner_id != current_user.id
    ):
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_BLOCK_NOT_FOUND",
                    "message": "차단 이력을 찾을 수 없습니다.",
                }
            }
        ), 404

    if block.status != "blocked":
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_BLOCK_NOT_ACTIVE",
                    "message": "현재 차단 중인 문서가 아닙니다.",
                }
            }
        ), 409

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            {
                "error": {
                    "code": "INVALID_JSON",
                    "message": "올바른 JSON 객체를 전송해주세요.",
                }
            }
        ), 400

    reason = data.get("reason")

    if not isinstance(reason, str):
        return jsonify(
            {
                "error": {
                    "code": "INVALID_REASON",
                    "message": "소명 사유를 입력해주세요.",
                }
            }
        ), 400

    reason = reason.strip()

    if not reason:
        return jsonify(
            {
                "error": {
                    "code": "EMPTY_REASON",
                    "message": "소명 사유를 입력해주세요.",
                }
            }
        ), 400

    existing = (
        DocumentUnblockRequest.query
        .filter(
            DocumentUnblockRequest.block_id == block.id,
            DocumentUnblockRequest.status == "pending",
        )
        .first()
    )

    if existing is not None:
        return jsonify(
            {
                "error": {
                    "code": "UNBLOCK_REQUEST_ALREADY_PENDING",
                    "message": "이미 처리 대기 중인 소명 요청이 있습니다.",
                }
            }
        ), 409

    unblock_request = DocumentUnblockRequest(
        block_id=block.id,
        requester_id=current_user.id,
        request_reason=reason,
        status="pending",
    )

    db.session.add(unblock_request)
    db.session.commit()

    return jsonify(
        {
            "data": {
                "id": unblock_request.id,
                "block_id": unblock_request.block_id,
                "status": unblock_request.status,
                "requested_at": to_iso(
                    unblock_request.requested_at,
                ),
            }
        }
    ), 201