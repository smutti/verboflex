"""Alembic runtime seam for VerboFlex migrations."""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from verboflex import models as models
from verboflex.db.base import Base

config = context.config

environment_database_url = os.environ.get("VERBOFLEX_DATABASE_URL")
if environment_database_url:
    config.set_main_option(
        "sqlalchemy.url",
        environment_database_url.replace("%", "%%"),
    )

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render migrations using only the configured URL."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations in a transaction on the configured database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
