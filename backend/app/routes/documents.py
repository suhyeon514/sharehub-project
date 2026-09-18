import json
import os
import uuid
from datetime import timezone

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import ActivityLog, Document, DocumentBlock, FileCleanupJob
from app.models.comment import Comment
from app.routes.auth import login_required
from app.services.document_permissions import (
    can_download_document,
    can_view_document,
    get_document_access,
    has_document_permission,
)
from app.services.document_blocks import (
    document_not_blocked_condition,
    is_document_blocked,
    blocked_response,
)
from app.services.file_cleanup import process_cleanup_job_safely


documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


ALLOWED_VISIBILITIES = {"private", "team"}

ALLOWED_EXTENSIONS = {
    "pdf",
    "txt",
    "csv",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "zip",
    "jpg",
    "jpeg",
    "png",
}


def allowed_file(filename):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS

def to_utc_iso(value):
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).isoformat()


def serialize_document_summary(document):
    return {
        "id": document.id,
        "title": document.title,
        "owner": {
            "id": document.owner.id,
            "username": document.owner.username,
        },
        "department": (
            {
                "id": document.department.id,
                "name": document.department.name,
            }
            if document.department
            else None
        ),
        "visibility": document.visibility,
        "original_filename": document.original_filename,
        "file_size": document.file_size,
        "created_at": to_utc_iso(document.created_at),
        "updated_at": to_utc_iso(document.updated_at),
    }



def serialize_document_detail(document, access):
    return {
        "id": document.id,
        "title": document.title,
        "description": document.description,
        "owner": {
            "id": document.owner.id,
            "username": document.owner.username,
        },
        "department": (
            {
                "id": document.department.id,
                "name": document.department.name,
            }
            if document.department
            else None
        ),
        "visibility": document.visibility,
        "original_filename": document.original_filename,
        "file_size": document.file_size,
        "content_type": document.content_type,
        "created_at": to_utc_iso(document.created_at),
        "updated_at": to_utc_iso(document.updated_at),
        "access": {
            "source": access["source"],
            "permission": access["permission"],
        },
    }


def serialize_comment(comment):
    return {
        "id": comment.id,
        "content": comment.content,
        "user": {
            "id": comment.user.id,
            "username": comment.user.username,
        },
        "created_at": to_utc_iso(comment.created_at),
    }


@documents_bp.route("/<int:document_id>", methods=["PATCH"])
@login_required
def update_document(
    document_id,
    current_user,
    current_session,
):
    # 공유 변경·차단 API와 동일하게 Document를 가장 먼저 잠근다.
    document = db.session.execute(
        db.select(Document)
        .where(Document.id == document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()

    if document is None:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    # Document 잠금 획득 이후 현재 접근 근거를 다시 계산한다.
    access = get_document_access(
        document,
        current_user,
        lock_share=True,
    )

    if not access["allowed"]:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    # REPEATABLE READ의 오래된 일반 조회가 아니라 locking read로
    # Document 잠금 이후의 활성 차단 상태를 확인한다.
    active_block = db.session.execute(
        db.select(DocumentBlock.id)
        .where(
            DocumentBlock.document_id == document.id,
            DocumentBlock.status == "blocked",
        )
        .with_for_update()
    ).scalar_one_or_none()

    if active_block is not None:
        return blocked_response()

    if not has_document_permission(access, "edit"):
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_EDIT_FORBIDDEN",
                    "message": "문서를 수정할 권한이 없습니다.",
                }
            }
        ), 403

    data = request.get_json(silent=True)

    allowed_fields = {"title", "description"}

    if not isinstance(data, dict):
        return jsonify(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "올바른 JSON 객체를 전송해주세요.",
                }
            }
        ), 400

    if not data:
        return jsonify(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "수정할 필드를 하나 이상 입력해주세요.",
                }
            }
        ), 400

    unknown_fields = set(data) - allowed_fields

    if unknown_fields:
        return jsonify(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "title과 description 필드만 수정할 수 있습니다.",
                }
            }
        ), 400

    normalized = {}

    if "title" in data:
        title = data["title"]

        if not isinstance(title, str):
            return jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "제목은 문자열이어야 합니다.",
                    }
                }
            ), 400

        title = title.strip()

        if not title:
            return jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "제목을 입력해주세요.",
                    }
                }
            ), 400

        if len(title) > 255:
            return jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "제목은 255자 이하로 입력해주세요.",
                    }
                }
            ), 400

        normalized["title"] = title

    if "description" in data:
        description = data["description"]

        if description is not None and not isinstance(description, str):
            return jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "설명은 문자열 또는 null이어야 합니다.",
                    }
                }
            ), 400

        if isinstance(description, str):
            description = description.strip()

            if not description:
                description = None

        if description is not None and len(description) > 5000:
            return jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "설명은 5000자 이하로 입력해주세요.",
                    }
                }
            ), 400

        normalized["description"] = description

    changed_fields = []

    if "title" in normalized and normalized["title"] != document.title:
        changed_fields.append("title")

    if (
        "description" in normalized
        and normalized["description"] != document.description
    ):
        changed_fields.append("description")

    # 정규화 후 실제 변경 없음:
    # updated_at과 감사 로그를 변경하지 않는다.
    if not changed_fields:
        db.session.commit()

        return jsonify(
            {
                "document": {
                    "id": document.id,
                    "title": document.title,
                    "description": document.description,
                    "updated_at": to_utc_iso(document.updated_at),
                }
            }
        ), 200

    try:
        if "title" in changed_fields:
            document.title = normalized["title"]

        if "description" in changed_fields:
            document.description = normalized["description"]

        db.session.add(
            ActivityLog(
                user_id=current_user.id,
                action_type="DOCUMENT_UPDATE",
                ip_address=request.remote_addr,
                detail=json.dumps(
                    {
                        "operation": "update",
                        "document_id": document.id,
                        "changed_fields": changed_fields,
                    }
                ),
            )
        )

        # updated_at/onupdate와 DB 생성 값을 응답 전에 확정한다.
        db.session.flush()
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    # commit 이후 DB 값을 다시 읽는다.
    db.session.refresh(document)

    return jsonify(
        {
            "document": {
                "id": document.id,
                "title": document.title,
                "description": document.description,
                "updated_at": to_utc_iso(document.updated_at),
            }
        }
    ), 200


@documents_bp.route("/<int:document_id>", methods=["DELETE"])
@login_required
def delete_document(
    document_id,
    current_user,
    current_session,
):
    # 공유 변경/PATCH와 동일하게 Document를 가장 먼저 잠근다.
    document = db.session.execute(
        db.select(Document)
        .where(Document.id == document_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()

    if document is None:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    # Document 잠금 이후 최신 접근 근거를 확인한다.
    # 개별 공유 역시 locking read로 최신 상태를 사용한다.
    access = get_document_access(
        document,
        current_user,
        lock_share=True,
    )

    if not access["allowed"]:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    # 접근 근거가 있는 사용자에게만 현재 차단 여부를 공개한다.
    active_block = db.session.execute(
        db.select(DocumentBlock.id)
        .where(
            DocumentBlock.document_id == document.id,
            DocumentBlock.status == "blocked",
        )
        .with_for_update()
    ).scalar_one_or_none()

    if active_block is not None:
        return blocked_response()

    # 삭제는 edit 공유 권한과 별개다.
    # 오직 현재 문서 소유자만 삭제할 수 있다.
    if document.owner_id != current_user.id:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_DELETE_FORBIDDEN",
                    "message": "문서를 삭제할 권한이 없습니다.",
                }
            }
        ), 403

    deleted_document_id = document.id
    cleanup_file_path = document.file_path

    try:
        # -----------------------------------------------------
        # 과거 차단 이력 보존
        #
        # Document FK는 RESTRICT이므로 Document 삭제 전에
        # 연결만 명시적으로 NULL 처리한다.
        # document_id_snapshot은 변경하지 않는다.
        # -----------------------------------------------------
        historical_blocks = db.session.execute(
            db.select(DocumentBlock)
            .where(
                DocumentBlock.document_id
                == deleted_document_id
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalars().all()

        for block in historical_blocks:
            block.document_id = None

        # FK RESTRICT 환경에서 block unlink를 먼저 DB에 반영한다.
        db.session.flush()

        # -----------------------------------------------------
        # DOCUMENT_DELETE 감사 로그
        # -----------------------------------------------------
        delete_log = ActivityLog(
            user_id=current_user.id,
            action_type="DOCUMENT_DELETE",
            detail=json.dumps(
                {
                    "operation": "delete",
                    "document_id": deleted_document_id,
                },
                ensure_ascii=False,
            ),
            ip_address=request.remote_addr,
        )

        db.session.add(delete_log)

        # -----------------------------------------------------
        # durable physical-file cleanup job
        #
        # Document FK를 두지 않고 snapshot만 보존한다.
        # -----------------------------------------------------
        cleanup_job = FileCleanupJob(
            document_id_snapshot=deleted_document_id,
            file_path=cleanup_file_path,
        )

        db.session.add(cleanup_job)

        # comments / shares는 Document relationship의
        # delete-orphan cascade를 사용한다.
        db.session.delete(document)

        # MariaDB의 RESTRICT FK를 실제 commit 전에 처리하도록
        # SQLAlchemy delete ordering을 여기서 실행한다.
        db.session.flush()

        # cleanup_job.id가 생성된 상태에서 원자적으로 commit한다.
        cleanup_job_id = cleanup_job.id

        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "document delete transaction failed: document_id=%s",
            document_id,
        )

        return jsonify(
            {
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "문서를 삭제하지 못했습니다.",
                }
            }
        ), 500

    # ---------------------------------------------------------
    # DB 삭제가 성공한 뒤 실제 파일 정리를 한 번 시도한다.
    #
    # 여기서 실패하더라도 문서 DB 삭제는 이미 완료됐으므로
    # DELETE 응답을 500으로 변경하지 않는다.
    # pending cleanup job은 CLI에서 재시도할 수 있다.
    # ---------------------------------------------------------
    try:
        process_cleanup_job_safely(cleanup_job_id)

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "immediate file cleanup failed: cleanup_job_id=%s",
            cleanup_job_id,
        )

    return "", 204


@documents_bp.route("/<int:document_id>", methods=["GET"])
@login_required
def get_document_detail(
    document_id,
    current_user,
    current_session,
):
    document = db.session.get(
        Document,
        document_id,
    )

    if document is None:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    access = get_document_access(
        document,
        current_user,
    )


    # if not access["allowed"]:
    #     return jsonify(
    #         {
    #             "error": {
    #                 "code": "DOCUMENT_NOT_FOUND",
    #                 "message": "문서를 찾을 수 없습니다.",
    #             }
    #         }
    #     ), 404

    if is_document_blocked(document.id):
        return blocked_response()

    # if not can_view_document(current_user, document):
    #     return jsonify(
    #         {
    #             "error": {
    #                 "code": "FORBIDDEN",
    #                 "message": "문서 접근 권한이 없습니다.",
    #             }
    #         }
    #     ), 403

    return jsonify(
        {
            "data": serialize_document_detail(
                document,
                access,
            )
        }
    ), 200


@documents_bp.route("/<int:document_id>/download", methods=["GET"])
@login_required
def download_document(
    document_id,
    current_user,
    current_session,
):
    document = db.session.get(Document, document_id)

    if document is None:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    access = get_document_access(
        document,
        current_user,
    )

    if not access["allowed"]:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    if is_document_blocked(document.id):
        return blocked_response()

    if not can_download_document(current_user, document):
        return jsonify(
            {
                "error": {
                    "code": "FORBIDDEN",
                    "message": "문서를 다운로드할 권한이 없습니다.",
                }
            }
        ), 403

    if not os.path.isfile(document.file_path):
        return jsonify(
            {
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": "저장된 파일을 찾을 수 없습니다.",
                }
            }
        ), 404

    return send_file(
        document.file_path,
        as_attachment=True,
        download_name=document.original_filename,
        mimetype=document.content_type,
    )

@documents_bp.route("/mine", methods=["GET"])
@login_required
def get_my_documents(current_user, current_session):
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    if page is None or page < 1:
        return jsonify(
            {
                "code": "INVALID_PAGE",
                "message": "page는 1 이상의 정수여야 합니다.",
            }
        ), 400

    if page_size is None or page_size < 1 or page_size > 100:
        return jsonify(
            {
                "code": "INVALID_PAGE_SIZE",
                "message": "page_size는 1 이상 100 이하의 정수여야 합니다.",
            }
        ), 400

    query = Document.query.filter(
        Document.owner_id == current_user.id,
        document_not_blocked_condition(Document.id),
    ).order_by(
        Document.created_at.desc(),
        Document.id.desc(),
    )

    pagination = query.paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )

    return jsonify(
        {
            "data": [
                serialize_document_summary(document)
                for document in pagination.items
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": pagination.total,
            },
        }
    ), 200


@documents_bp.route("", methods=["POST"])
@login_required
def upload_document(current_user, current_session):
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    visibility = (request.form.get("visibility") or "private").strip().lower()

    uploaded_file = request.files.get("file")

    # 제목 검증
    if not title:
        return jsonify({"error": "title is required"}), 400

    if len(title) > 255:
        return jsonify({"error": "title must be 255 characters or fewer"}), 400

    # 공개 범위 검증
    if visibility not in ALLOWED_VISIBILITIES:
        return jsonify(
            {
                "error": "invalid visibility",
                "allowed": sorted(ALLOWED_VISIBILITIES),
            }
        ), 400

    # 부서가 없는 사용자는 team 문서를 만들 수 없음
    if visibility == "team" and current_user.department_id is None:
        return jsonify(
            {"error": "user without a department cannot create a team document"}
        ), 400

    # 파일 검증
    if uploaded_file is None:
        return jsonify({"error": "file is required"}), 400

    original_filename = uploaded_file.filename or ""

    if not original_filename:
        return jsonify({"error": "filename is required"}), 400

    if len(original_filename) > 255:
        return jsonify({"error": "filename must be 255 characters or fewer"}), 400

    if not allowed_file(original_filename):
        return jsonify({"error": "file type is not allowed"}), 400

    # 실제 저장 파일명은 사용자가 올린 이름을 그대로 쓰지 않고 UUID 사용
    safe_filename = secure_filename(original_filename)

    if "." not in safe_filename:
        extension = original_filename.rsplit(".", 1)[1].lower()
    else:
        extension = safe_filename.rsplit(".", 1)[1].lower()

    stored_filename = f"{uuid.uuid4().hex}.{extension}"

    upload_dir = os.path.abspath(current_app.config["UPLOAD_DIR"])
    os.makedirs(upload_dir, exist_ok=True)

    stored_path = os.path.join(upload_dir, stored_filename)

    try:
        uploaded_file.save(stored_path)

        file_size = os.path.getsize(stored_path)

        document = Document(
            title=title,
            description=description or None,
            owner_id=current_user.id,
            department_id=current_user.department_id,
            visibility=visibility,
            file_path=stored_path,
            original_filename=original_filename,
            file_size=file_size,
            content_type=uploaded_file.mimetype or None,
        )

        db.session.add(document)
        db.session.commit()

    except Exception:
        db.session.rollback()

        # DB 저장 실패 시 디스크에 남은 파일 정리
        if os.path.exists(stored_path):
            try:
                os.remove(stored_path)
            except OSError:
                pass

        current_app.logger.exception("document upload failed")

        return jsonify({"error": "failed to upload document"}), 500

    return (
        jsonify(
            {
                "document": {
                    "id": document.id,
                    "title": document.title,
                    "description": document.description,
                    "visibility": document.visibility,
                    "owner_id": document.owner_id,
                    "department_id": document.department_id,
                    "original_filename": document.original_filename,
                    "file_size": document.file_size,
                    "content_type": document.content_type,
                    "created_at": (
                        document.created_at.isoformat()
                        if document.created_at
                        else None
                    ),
                }
            }
        ),
        201,
    )


#댓글 목록 조회 API
@documents_bp.route("/<int:document_id>/comments", methods=["GET"])
@login_required
def get_document_comments(
    document_id,
    current_user,
    current_session,
):
    document = db.session.get(
        Document,
        document_id,
    )

    if document is None:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    access = get_document_access(
        document,
        current_user,
    )

    if not access["allowed"]:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    if is_document_blocked(document.id):
        return blocked_response()

    if not can_view_document(current_user, document):
        return jsonify(
            {
                "error": {
                    "code": "FORBIDDEN",
                    "message": "문서 접근 권한이 없습니다.",
                }
            }
        ), 403

    comments = (
        Comment.query
        .filter_by(document_id=document.id)
        .order_by(
            Comment.created_at.asc(),
            Comment.id.asc(),
        )
        .all()
    )

    return jsonify(
        {
            "data": [
                serialize_comment(comment)
                for comment in comments
            ]
        }
    ), 200

#댓글 작성 조회 API
@documents_bp.route("/<int:document_id>/comments", methods=["POST"])
@login_required
def create_document_comment(
    document_id,
    current_user,
    current_session,
):
    document = db.session.get(
        Document,
        document_id,
    )

    if document is None:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    access = get_document_access(
        document,
        current_user,
    )

    if not access["allowed"]:
        return jsonify(
            {
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "문서를 찾을 수 없습니다.",
                }
            }
        ), 404

    if is_document_blocked(document.id):
        return blocked_response()

    if not can_view_document(current_user, document):
        return jsonify(
            {
                "error": {
                    "code": "FORBIDDEN",
                    "message": "문서 접근 권한이 없습니다.",
                }
            }
        ), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            {
                "code": "INVALID_JSON",
                "message": "올바른 JSON 객체를 전송해주세요.",
            }
        ), 400

    content = data.get("content")

    if not isinstance(content, str):
        return jsonify(
            {
                "code": "INVALID_CONTENT",
                "message": "댓글 내용은 문자열이어야 합니다.",
            }
        ), 400

    content = content.strip()

    if not content:
        return jsonify(
            {
                "code": "EMPTY_CONTENT",
                "message": "댓글 내용을 입력해주세요.",
            }
        ), 400

    if len(content) > 2000:
        return jsonify(
            {
                "code": "CONTENT_TOO_LONG",
                "message": "댓글은 2000자 이하로 입력해주세요.",
            }
        ), 400

    comment = Comment(
        document_id=document.id,
        user_id=current_user.id,
        content=content,
    )

    db.session.add(comment)
    db.session.commit()

    return jsonify(
        {
            "data": serialize_comment(comment)
        }
    ), 201