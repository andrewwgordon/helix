"""Application configuration classes.

Loaded by :func:`app.create_app` via ``app.config.from_object``.
"""

import os

basedir = os.path.abspath(os.path.dirname(__file__))

# Default SQLite database file lives next to the project root.
_DEFAULT_SQLITE_URI = "sqlite:///" + os.path.join(basedir, "plm.db")


class BaseConfig:
    """Settings shared by every environment."""

    # --- Flask core -----------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    WTF_CSRF_ENABLED = True

    # --- Flask-AppBuilder ----------------------------------------------
    APP_NAME = "Helix PLM"
    APP_THEME = "spacelab.css"
    # Standard FAB IndexView subclass rendering the PLM summary dashboard.
    FAB_INDEX_VIEW = "app.dashboard.SummaryIndexView"
    # Let FAB create/upgrade its own security tables on first boot.
    FAB_CREATE_DB = True
    # Seed reference data and roles on startup (idempotent).
    SEED_REFERENCE_DATA = True

    # --- Babel ----------------------------------------------------------
    BABEL_DEFAULT_LOCALE = "en"
    BABEL_DEFAULT_TIMEZONE = "UTC"

    # --- SQLAlchemy / SQLite -------------------------------------------
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Required because FAB may touch the connection from worker threads.
        "connect_args": {"check_same_thread": False},
    }

    # --- Document uploads ----------------------------------------------
    UPLOAD_FOLDER = os.path.join(basedir, "uploads")
    FILE_ALLOWED_EXTENSIONS = [
        "txt", "pdf", "doc", "docx", "xls", "xlsx", "csv",
        "png", "jpg", "jpeg", "gif", "svg", "zip",
    ]


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE_URI)


class TestConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    # FAB must create its own security tables on init; our app tables are
    # created by db.create_all() in the factory.
    FAB_CREATE_DB = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE_URI)
    # Alembic owns schema creation/upgrades in production.
    FAB_CREATE_DB = False


config = {
    "development": DevelopmentConfig,
    "test": TestConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
