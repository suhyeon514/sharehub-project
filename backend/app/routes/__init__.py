from flask import Flask

from app.config import Config
from app.extensions import db, migrate


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    from app import models  # noqa: F401

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    @app.route("/api/health")
    def health():
        return {
            "status": "ok",
            "service": "sharehub-api",
        }

    return app