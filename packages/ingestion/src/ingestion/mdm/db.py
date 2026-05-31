"""Warehouse engine for the MDM linker.

Splink's Postgres backend runs against the same warehouse dbt builds into, so the
conformed input tables and the cluster outputs never leave the database.

Resolution order for the DSN:
    MDM_DATABASE_URL  ->  DATABASE_URL  ->  local dbt warehouse default
The default points at the local dbt warehouse (localhost:5433/open_navigator),
matching dbt_project profiles.yml.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

LOCAL_WAREHOUSE_DSN = "postgresql://postgres:password@localhost:5433/open_navigator"


def warehouse_dsn() -> str:
    url = os.getenv("MDM_DATABASE_URL") or os.getenv("DATABASE_URL") or LOCAL_WAREHOUSE_DSN
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


# Splink's Postgres backend resolves input tables by BARE name via search_path
# (it does not parse schema-qualified names), so the engine puts the MDM schemas
# on the path. intermediate = conformed inputs, bronze = filtered views + outputs.
SEARCH_PATH = "intermediate,bronze,public"


def get_engine() -> Engine:
    """SQLAlchemy engine Splink's PostgresAPI binds to."""
    return create_engine(
        warehouse_dsn(),
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={SEARCH_PATH}"},
    )
