import logging
from pprint import pp
from uuid import uuid4

from flask import Flask, g, request

from app.config import Config
from app.extensions import db, migrate


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)

    # Flask 로거 기본 레벨은 WARNING이라 비디버그 실행에서 INFO 요청 로그가 누락된다.
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def assign_request_id():
        g.request_id = str(uuid4())

    @app.after_request
    def log_request_and_add_request_id(response):
        request_id = g.get("request_id")

        response.headers["X-Request-ID"] = request_id

        app.logger.info(
            "http_request request_id=%s method=%s path=%s status=%s user_id=%s",
            request_id,
            request.method,
            request.path,
            response.status_code,
            g.get("current_user_id"),
        )

        return response

    db.init_app(app)
    migrate.init_app(app, db)
    # 모델을 Migration이 인식하도록 import
    from app import models  # noqa: F401

    # Blueprint 등록
    from app.routes.auth import auth_bp
    from app.routes.documents import documents_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(dashboard_bp)

    from app.routes.shares import shares_bp
    app.register_blueprint(shares_bp)

    from app.routes.users import users_bp
    app.register_blueprint(users_bp)

    from app.routes.document_lists import document_lists_bp
    app.register_blueprint(document_lists_bp)

    from app.routes.search import search_bp
    app.register_blueprint(search_bp)

    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)
    from app.routes.admin_reviews import admin_reviews_bp
    app.register_blueprint(admin_reviews_bp)

    from app.routes.my_document_blocks import (
        my_document_blocks_bp,
        document_block_requests_bp,
    )
    app.register_blueprint(my_document_blocks_bp)
    app.register_blueprint(document_block_requests_bp)

    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "sharehub-api"}

    # Flask CLI 등록
    from app.cli import register_cli
    register_cli(app)

    return app
