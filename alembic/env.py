"""Alembic environment — URL is injected by app.db.run_migrations."""
from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401 — register all tables on metadata
from app.models.base import Base

config = context.config

# Optional: frozen builds may omit logging.config; migrations do not need it.
# disable_existing_loggers=False so Alembic does not mute the app's
# jayram_dairy activity logger that setup_logging already configured.
if config.config_file_name is not None:
    try:
        from logging.config import fileConfig

        fileConfig(config.config_file_name, disable_existing_loggers=False)
    except ModuleNotFoundError:
        pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
