from functools import wraps
from flask import jsonify
from app.routes.auth import login_required


def admin_required(view):
    """세션 인증 후 매 요청에서 DB의 현재 역할을 확인한다."""
    @wraps(view)
    def wrapped(*args, current_user, current_session, **kwargs):
        if current_user.role != "admin":
            return jsonify({"message": "관리자만 접근할 수 있습니다."}), 403
        return view(*args, current_user=current_user, current_session=current_session, **kwargs)
    return login_required(wrapped)
