"""Alembic migration environment for Helix PLM.

Targets the shared Flask-AppBuilder declarative metadata, which contains both
the ``ab_*`` security tables and the PLM domain tables.

SQLite has limited ``ALTER TABLE`` support, so migrations run in **batch mode**
(``render_as_batch=True``); Alembic then recreates tables when needed.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the project root importable so ``config`` and ``app`` resolve.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask_appbuilder.models.sqla import Base as FabBase  # noqa: E402

from config import config as app_config  # noqa: E402

# Interpret the config file for Python logging.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the database URL from the application config (defaults to development).
config_name = os.environ.get("FLASK_CONFIG", "development")
config.set_main_option(
    "sqlalchemy.url", app_config[config_name].SQLALCHEMY_DATABASE_URI
)

# Register the security tables (ab_*) on the shared metadata. Importing the
# models has no side effects; no application/schema is created here.
from flask_appbuilder.security.sqla import models as _fab_security_models  # noqa: E402,F401

# Import the application's domain models so they register on the metadata.
import app.models  # noqa: E402,F401

# Single source of schema truth: FAB's declarative metadata.
target_metadata = FabBase.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with a live connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
