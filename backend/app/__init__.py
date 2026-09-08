from flask import Flask

from app.config import Config
from app.extensions import db, migrate


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    # 7개 모델을 Migration이 인식하도록 import
    from app import models  # noqa: F401

    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "sharehub-api"}

    return app
