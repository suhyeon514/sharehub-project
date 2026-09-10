import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import Session, User


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/api/auth",
)


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify(
            {
                "message": "아이디와 비밀번호를 입력해주세요."
            }
        ), 400

    user = User.query.filter_by(username=username).first()

    if user is None:
        return jsonify(
            {
                "message": "아이디 또는 비밀번호가 올바르지 않습니다."
            }
        ), 401

    try:
        password_valid = check_password_hash(
            user.password_hash,
            password,
        )
    except (ValueError, TypeError):
        password_valid = False

    if not password_valid:
        return jsonify(
            {
                "message": "아이디 또는 비밀번호가 올바르지 않습니다."
            }
        ), 401

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=8)

    session = Session(
        user_id=user.id,
        session_token=secrets.token_urlsafe(48),
        created_at=now,
        expires_at=expires_at,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        is_active=True,
    )

    db.session.add(session)
    db.session.commit()

    return jsonify(
        {
            "message": "로그인되었습니다.",
            "token": session.session_token,
            "expires_at": expires_at.isoformat(),
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "department_id": user.department_id,
            },
        }
    ), 200
