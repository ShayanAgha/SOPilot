"""
SOPilot configuration.

Everything secret or environment-specific is read from environment
variables (see .env.example). Nothing sensitive is hardcoded here.
"""
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # --- Core Flask / security ---
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        # Fail loudly in production; fall back only for local dev convenience.
        SECRET_KEY = "dev-only-insecure-key-change-me"

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- Database ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- File storage ---
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads")
    )
    VECTOR_STORE_DIR = os.environ.get(
        "VECTOR_STORE_DIR", os.path.join(BASE_DIR, "vector_store")
    )
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max PDF upload
    ALLOWED_EXTENSIONS = {"pdf"}

    # --- RAG / LLM settings (used from Phase 2 onward) ---
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")
    EMBEDDING_MODEL_NAME = os.environ.get(
        "EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-base"
    )
    TOP_K = int(os.environ.get("TOP_K", 10))
    SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", 0.72))
    CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 800))
    CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 120))

    # --- Pagination ---
    LOGS_PER_PAGE = int(os.environ.get("LOGS_PER_PAGE", 25))

    # SOP categories used across upload forms, filters, and dashboards.
    SOP_CATEGORIES = [
        "HR",
        "Finance",
        "IT-Security",
        "Operations",
        "Compliance",
        "Other",
    ]


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
