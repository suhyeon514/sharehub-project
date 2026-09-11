import os
import uuid

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.document import Document
from app.routes.auth import login_required


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
