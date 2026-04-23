from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv
import os

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

# Alembic config
config = context.config

# Load .env and set DATABASE_URL into alembic.ini variable
load_dotenv()
config.set_main_option("DATABASE_URL", os.getenv("DATABASE_URL", ""))

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base + models so Alembic can "see" them
from app.core.database import Base
from app.models.user import User
from app.models.client import Client
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.company import Company
from app.models.group import Group
from app.models.expense import Expense
from app.models.contract import Contract

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
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

#GOOGLE_CALENDAR_ID=5e6647d4009365b5c8a2662fe63c9172994250a199de03d908d0fedf26b69993@group.calendar.google.com
#GOOGLE_SERVICE_ACCOUNT_FILE=google-calendar.json
#GOOGLE_CALENDAR_TIMEZONE=Europe/Lisbon
