"""Helix PLM application factory.

Usage::

    from app import create_app

    app = create_app()
    app.run()
"""

import os

from flask import Flask
from flask_appbuilder import AppBuilder
from flask_appbuilder.models.sqla import Base as FabBase
from flask_appbuilder.models.sqla.base import SQLA

# Importing the module registers the SQLite ``connect`` event listener.
from app import database  # noqa: F401

db = SQLA()
appbuilder = AppBuilder()


def create_app(config_name=None):
    """Create and configure the Flask application."""
    config_name = config_name or os.environ.get("FLASK_CONFIG", "development")

    app = Flask(__name__)
    from config import config as config_map

    app.config.from_object(config_map[config_name])

    upload_folder = app.config.get("UPLOAD_FOLDER")
    if upload_folder:
        os.makedirs(upload_folder, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        appbuilder.init_app(app, db.session)

        # Import views/models after appbuilder init. Models inherit from
        # ``flask_appbuilder.Model`` and share FAB's declarative metadata, so
        # they must be imported before creating the schema.
        from app import models, views  # noqa: F401,E402

        # Create the full schema (FAB security tables + PLM tables) from the
        # shared metadata. Idempotent. Disable with FAB_CREATE_DB=False when
        # Alembic is the sole owner of schema changes (e.g. production).
        if app.config.get("FAB_CREATE_DB", True):
            FabBase.metadata.create_all(db.engine)

        # Seed reference data (and roles) on startup. Idempotent.
        if app.config.get("SEED_REFERENCE_DATA", True):
            from app.seed import seed_all  # noqa: E402

            seed_all(db.session, appbuilder.sm)

    from app.cli import register_cli  # noqa: E402

    register_cli(app)

    return app
