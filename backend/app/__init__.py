from flask import Flask

from app.config import Config
from app.extensions import db, migrate


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config is not None:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)

    # 7개 모델을 Migration이 인식하도록 import
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

    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "sharehub-api"}

    return app
