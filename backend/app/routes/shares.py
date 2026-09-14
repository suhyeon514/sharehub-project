import json

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import ActivityLog, Document, DocumentBlock, DocumentShare, User
from app.routes.auth import login_required
from app.services.document_blocks import blocked_response
from app.services.document_permissions import get_document_access


shares_bp = Blueprint("shares", __name__, url_prefix="/api/documents")


def share_document_access(document_id, current_user, forbidden_message, *, lock=False):
    query = db.select(Document).where(Document.id == document_id)
    if lock:
        # 관리자 차단 처리도 문서부터 잠가야 공유 변경과 직렬화된다.
        query = query.with_for_update().execution_options(populate_existing=True)
    document = db.session.execute(query).scalar_one_or_none()
    if document is None or not get_document_access(document, current_user)["allowed"]:
        return None, (jsonify({"error": {
            "code": "DOCUMENT_NOT_FOUND", "message": "문서를 찾을 수 없습니다.",
        }}), 404)

    block_query = db.select(DocumentBlock.id).where(
        DocumentBlock.document_id == document_id,
        DocumentBlock.status == "blocked",
    )
    if lock:
        # REPEATABLE READ에서도 인증 조회 시점의 스냅샷이 아닌
        # 문서 잠금 대기 이후 최신 차단을 확인하는 locking read를 사용한다.
        block_query = block_query.with_for_update()
    if db.session.execute(block_query).scalar_one_or_none() is not None:
        return None, blocked_response()
    if document.owner_id != current_user.id:
        return None, (jsonify({"message": forbidden_message}), 403)
    return document, None


@shares_bp.get("/<int:document_id>/shares")
@login_required
def list_shares(document_id, current_user, current_session):
    document, error = share_document_access(
        document_id, current_user, "공유 설정을 조회할 권한이 없습니다.",
    )
    if error is not None:
        return error

    shares = db.session.execute(
        db.select(DocumentShare)
        .options(joinedload(DocumentShare.shared_with))
        .where(DocumentShare.document_id == document.id)
        .order_by(DocumentShare.id)
    ).scalars().all()

    return jsonify({
        "document": {"id": document.id, "title": document.title},
        "shares": [
            {
                "id": share.id,
                "shared_with": {
                    "id": share.shared_with.id,
                    "username": share.shared_with.username,
                },
                "permission": share.permission,
            }
            for share in shares
        ],
    })


@shares_bp.post("/<int:document_id>/shares")
@login_required
def create_share(document_id, current_user, current_session):
    document, error = share_document_access(
        document_id, current_user, "공유를 생성할 권한이 없습니다.", lock=True,
    )
    if error is not None:
        return error

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"message": "올바른 JSON 객체를 전송해주세요."}), 400
    target_id = data.get("shared_with_id")
    permission = data.get("permission")
    if type(target_id) is not int or target_id <= 0:
        return jsonify({"message": "올바른 공유 대상 ID를 입력해주세요."}), 400
    if not isinstance(permission, str) or permission not in ("view", "download", "edit"):
        return jsonify({"message": "공유 권한은 view, download, edit 중 하나여야 합니다."}), 400
    if target_id == current_user.id:
        return jsonify({"message": "자기 자신에게 공유할 수 없습니다."}), 400
    target = db.session.get(User, target_id)
    if target is None:
        return jsonify({"message": "공유 대상 사용자가 존재하지 않습니다."}), 400

    existing_query = db.select(DocumentShare).where(
        DocumentShare.document_id == document_id,
        DocumentShare.shared_with_id == target_id,
    ).with_for_update()
    if db.session.execute(existing_query).scalar_one_or_none() is not None:
        return jsonify({"message": "이미 공유 중인 사용자입니다."}), 409

    share = DocumentShare(
        document_id=document_id, shared_by_id=current_user.id,
        shared_with_id=target_id, permission=permission,
    )
    try:
        db.session.add(share)
        db.session.flush()
        result = {
            "id": share.id,
            "shared_with": {"id": target.id, "username": target.username},
            "permission": share.permission,
        }
        db.session.add(ActivityLog(
            user_id=current_user.id, action_type="DOCUMENT_SHARE",
            ip_address=request.remote_addr,
            detail=json.dumps({
                "operation": "create", "document_id": document_id,
                "share_id": share.id, "shared_with_id": target_id,
                "before_permission": None, "after_permission": permission,
            }),
        ))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if db.session.execute(existing_query).scalar_one_or_none() is not None:
            return jsonify({"message": "이미 공유 중인 사용자입니다."}), 409
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return jsonify({"share": result}), 201


@shares_bp.route("/<int:document_id>/shares/<int:share_id>", methods=["PATCH", "DELETE"])
@login_required
def change_share(document_id, share_id, current_user, current_session):
    document, error = share_document_access(
        document_id, current_user, "공유를 관리할 권한이 없습니다.", lock=True,
    )
    if error is not None:
        return error

    # 문서 소속을 함께 제한하고 동시 변경 시 변경 전 권한을 직렬화한다.
    share = db.session.execute(
        db.select(DocumentShare).where(
            DocumentShare.id == share_id,
            DocumentShare.document_id == document_id,
        ).with_for_update()
    ).scalar_one_or_none()
    if share is None:
        return jsonify({"message": "공유 내역을 찾을 수 없습니다."}), 404

    deleting = request.method == "DELETE"
    permission = None
    if not deleting:
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) != {"permission"}:
            return jsonify({"message": "permission 필드만 입력해주세요."}), 400
        permission = data["permission"]
        if not isinstance(permission, str) or permission not in ("view", "download", "edit"):
            return jsonify({"message": "공유 권한은 view, download, edit 중 하나여야 합니다."}), 400

    before = share.permission
    result = {
        "id": share.id,
        "shared_with": {"id": share.shared_with.id, "username": share.shared_with.username},
        "permission": permission,
    }
    # 같은 권한 저장은 성공으로 응답하되 변경 로그를 중복 생성하지 않는다.
    if not deleting and before == permission:
        return jsonify({"share": result})

    try:
        db.session.add(ActivityLog(
            user_id=current_user.id, action_type="DOCUMENT_SHARE",
            ip_address=request.remote_addr,
            detail=json.dumps({
                "operation": "delete" if deleting else "update",
                "document_id": document_id, "share_id": share.id,
                "shared_with_id": share.shared_with_id,
                "before_permission": before, "after_permission": permission,
            }),
        ))
        if deleting:
            db.session.delete(share)
        else:
            share.permission = permission
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    if deleting:
        return jsonify({"deleted_share_id": share_id})
    return jsonify({"share": result})
