"""Small shared sync-DB helper for the benchmark-source loaders (#1392).

Resolves the warehouse DSN from the environment (``OPEN_NAVIGATOR_DATABASE_URL``,
then ``DATABASE_URL``), strips the async driver suffix, and returns a SQLAlchemy
engine. The DSN is never logged.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

STATEMENT_TIMEOUT_MS = 120_000


def resolve_dsn() -> str:
    dsn = os.environ.get("OPEN_NAVIGATOR_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("Set OPEN_NAVIGATOR_DATABASE_URL (or DATABASE_URL) to the warehouse DSN")
    dsn = dsn.replace("+asyncpg", "")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    return dsn


def get_engine() -> Engine:
    return create_engine(
        resolve_dsn(),
        pool_pre_ping=True,
        connect_args={"options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}"},
    )
