import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")

    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
