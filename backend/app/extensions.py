"""
Flask 확장 인스턴스 분리 파일
- 순환 import(app/__init__.py <-> models) 방지를 위해
  db, migrate 객체를 별도 파일에 둔다. (문서 STEP 4 구조 기준)
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
