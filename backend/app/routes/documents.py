import os
import uuid
from datetime import timezone

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.comment import Comment
from app.models.document import Document
from app.routes.auth import login_required
from app.models.document_share import DocumentShare


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
        "file_size": document.file_size,
        "created_at": to_utc_iso(document.created_at),
        "updated_at": to_utc_iso(document.updated_at),
    }



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
        share_permission = share.permission

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
    required_level = PERMISSION_LEVELS.get(required_permission, 0)

    return current_level >= required_level


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
                "code": "NOT_FOUND",
                "message": "문서를 찾을 수 없습니다.",
            }
        ), 404

    access = get_document_access(
        document,
        current_user,
    )

    if not access["allowed"]:
        return jsonify(
            {
                "code": "FORBIDDEN",
                "message": "문서 접근 권한이 없습니다.",
            }
        ), 403

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
                "code": "NOT_FOUND",
                "message": "문서를 찾을 수 없습니다.",
            }
        ), 404

    access = get_document_access(
        document,
        current_user,
    )

    if not has_document_permission(access, "download"):
        return jsonify(
            {
                "code": "FORBIDDEN",
                "message": "문서를 다운로드할 권한이 없습니다.",
            }
        ), 403

    if not os.path.isfile(document.file_path):
        return jsonify(
            {
                "code": "FILE_NOT_FOUND",
                "message": "저장된 파일을 찾을 수 없습니다.",
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

    query = Document.query.filter_by(
        owner_id=current_user.id
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
                "code": "NOT_FOUND",
                "message": "문서를 찾을 수 없습니다.",
            }
        ), 404

    access = get_document_access(
        document,
        current_user,
    )

    if not has_document_permission(access, "view"):
        return jsonify(
            {
                "code": "FORBIDDEN",
                "message": "문서 접근 권한이 없습니다.",
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
                "code": "NOT_FOUND",
                "message": "문서를 찾을 수 없습니다.",
            }
        ), 404

    access = get_document_access(
        document,
        current_user,
    )

    if not has_document_permission(access, "view"):
        return jsonify(
            {
                "code": "FORBIDDEN",
                "message": "문서 접근 권한이 없습니다.",
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