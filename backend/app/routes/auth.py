import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

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
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            {
                "message": "올바른 JSON 객체를 전송해주세요."
            }
        ), 400

    username = data.get("username")
    password = data.get("password")

    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(
            {
                "message": "아이디와 비밀번호는 문자열이어야 합니다."
            }
        ), 400

    username = username.strip()

    if not username or not password:
        return jsonify(
            {
                "message": "아이디와 비밀번호를 입력해주세요."
            }
        ), 400

    user = User.query.filter_by(
        username=username
    ).first()

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
        user_agent=request.headers.get(
            "User-Agent"
        ),
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


def get_bearer_token():
    authorization = request.headers.get(
        "Authorization",
        "",
    )

    if not authorization.startswith("Bearer "):
        return None

    token = authorization.removeprefix(
        "Bearer "
    ).strip()

    if not token:
        return None

    return token


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        token = get_bearer_token()

        if not token:
            return jsonify(
                {
                    "message": "인증이 필요합니다."
                }
            ), 401

        session = Session.query.filter_by(
            session_token=token,
            is_active=True,
        ).first()

        if session is None:
            return jsonify(
                {
                    "message": "유효하지 않은 세션입니다."
                }
            ), 401

        now = datetime.now(timezone.utc)

        expires_at = session.expires_at

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        if expires_at <= now:
            session.is_active = False
            db.session.commit()

            return jsonify(
                {
                    "message": "세션이 만료되었습니다."
                }
            ), 401

        user = db.session.get(
            User,
            session.user_id,
        )

        if user is None:
            session.is_active = False
            db.session.commit()

            return jsonify(
                {
                    "message": "사용자 정보를 찾을 수 없습니다."
                }
            ), 401

        return view(
            *args,
            current_user=user,
            current_session=session,
            **kwargs,
        )

    return wrapped_view


@auth_bp.get("/me")
@login_required
def me(current_user, current_session):
    expires_at = current_session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    return jsonify(
        {
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "role": current_user.role,
                "department_id": current_user.department_id,
            },
            "session": {
                "expires_at": expires_at.isoformat(),
            },
        }
    ), 200


@auth_bp.post("/logout")
@login_required
def logout(current_user, current_session):
    current_session.is_active = False
    db.session.commit()

    return jsonify(
        {
            "message": "로그아웃되었습니다."
        }
    ), 200