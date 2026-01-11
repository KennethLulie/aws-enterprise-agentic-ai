"""
Alembic migration environment configuration.

This module configures Alembic to use the database URL from the application
settings, supporting both local development and AWS deployment.

The database URL is loaded from:
- Local: .env file or constructed from postgres_* settings
- AWS: Secrets Manager via settings module
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# Add backend/src to path for imports
# This allows importing from src.config without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.settings import get_settings  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None


def get_database_url() -> str:
    """
    Get database URL from settings.

    Returns:
        str: The database connection URL.

    Raises:
        RuntimeError: If DATABASE_URL is not configured.
    """
    settings = get_settings()
    url = settings.database_url

    if not url:
        raise RuntimeError(
            "DATABASE_URL not configured. "
            "Set DATABASE_URL environment variable or configure postgres_* settings."
        )

    return url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the
    Engine creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate
    a connection with the context.
    """
    url = get_database_url()

    # Create engine directly with URL from settings
    # Use NullPool for migrations (single connection, no pooling needed)
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
