from functools import wraps
from flask import jsonify
from app.routes.auth import login_required


def admin_required(view):
    """VULNERABLE LAB: 인증은 수행하지만 관리자 역할 검증은 누락한다."""
    @wraps(view)
    def wrapped(*args, current_user, current_session, **kwargs):

        # ---------------------------------------------------------
        # VULNERABLE LAB: Admin Role Bypass
        #
        # 취약점:
        # login_required를 통한 사용자 인증은 수행하지만,
        # 관리자 API 실행에 필요한 role == "admin" 검증을
        # 수행하지 않는다.
        #
        # 결과:
        # role="user"인 일반 사용자도 /api/admin/* 관리자
        # 기능에 접근할 수 있다.
        #
        # 정상 구현:
        # if current_user.role != "admin":
        #     return jsonify(
        #         {"message": "관리자만 접근할 수 있습니다."}
        #     ), 403
        # ---------------------------------------------------------

        # INTENTIONALLY VULNERABLE:
        # 관리자 역할(Role Authorization) 검증 누락

        return view(
            *args,
            current_user=current_user,
            current_session=current_session,
            **kwargs,
        )

    # Authentication은 그대로 유지
    return login_required(wrapped)
