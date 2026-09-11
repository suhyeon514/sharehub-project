from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import User
from app.routes.auth import login_required


users_bp = Blueprint("users", __name__, url_prefix="/api/users")


@users_bp.get("")
@login_required
def search_users(current_user, current_session):
    query = request.args.get("q", "").strip()
    if len(query) > 50:
        return jsonify({"message": "검색어는 50자 이내로 입력해주세요."}), 400
    if not query:
        return jsonify({"users": []})
    users = db.session.execute(
        db.select(User)
        .where(User.username.contains(query, autoescape=True))
        .order_by(User.username, User.id)
        .limit(20)
    ).scalars().all()
    return jsonify({"users": [{"id": user.id, "username": user.username} for user in users]})
