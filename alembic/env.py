import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load DB and Base
from backend.database import Base, DATABASE_URL

# Import ALL models explicitly so metadata loads
from backend.models import (
    BrokerTrade,
    BankTxn,
    Holding,
    NavLog,
    RuleDefinition,
    ReconBreak,
    ReconLog,
    ReconProposal,
    RuleMemory,
    LearningEvent,
)

# Alembic Config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell Alembic what metadata to scan
target_metadata = Base.metadata


def run_migrations_online():
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations not supported.")
else:
    run_migrations_online()
