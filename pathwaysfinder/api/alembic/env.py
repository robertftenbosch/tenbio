"""Alembic environment for tenbio/pathwaysfinder.

Imports Base.metadata from app.database so that `alembic revision --autogenerate`
can detect model changes going forward. Reads DATABASE_URL from the environment
(same var used by docker-compose), falling back to the SQLite path used locally.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make `app` importable when Alembic is invoked from api/ directory
sys.path.insert(0, os.getcwd())

from app.database import Base  # noqa: E402
# Import models so their metadata is registered on Base
from app.models import parts as _parts  # noqa: F401,E402
from app.models import pathway as _pathway  # noqa: F401,E402


config = context.config

# Let the environment override the URL (docker-compose sets DATABASE_URL)
db_url = os.getenv("DATABASE_URL", "sqlite:///./parts.db")
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=db_url.startswith("sqlite"),  # needed for ALTER on SQLite
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=db_url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
