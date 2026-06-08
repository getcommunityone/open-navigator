"""
Database connection and session management
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator

from api.models import Base

# Database URL priority:
# 1. NEON_DATABASE_URL_DEV (local development with PostgreSQL)
# 2. NEON_DATABASE_URL (production Neon PostgreSQL)
# 3. DATABASE_URL (backwards compatibility)
# 4. SQLite fallback (no setup required)
DATABASE_URL = os.getenv(
    "NEON_DATABASE_URL_DEV",
    os.getenv(
        "NEON_DATABASE_URL",
        os.getenv(
            "DATABASE_URL",
            "sqlite:///./data/users.db"
        )
    )
)

# Handle PostgreSQL URL format for SQLAlchemy 2.0+
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ---------------------------------------------------------------------------
# Serving schema (gold/public split).
#
# The warehouse is split into two Postgres schemas in open_navigator:
#   * `public` — ONLY the API-served relations, as views over gold; the
#     person-graph PII is absent and `contact_official` is PII-light. This is
#     what the PUBLIC API serves (default).
#   * `gold`   — the FULL warehouse (incl. the person graph, un-redacted). A
#     PRIVATE/internal API instance reads this by setting API_DB_SCHEMA=gold.
#
# API_DB_SCHEMA names the DATA schema (default `public`). Table references in
# route SQL are UNqualified so they resolve via search_path. The data pools
# (asyncpg) use `search_path = <API_DB_SCHEMA>, public` — the data schema first,
# `public` as the fallback for the operational/ORM tables (user/social_follows/
# prefs) which ALWAYS live in public. The ORM engine below uses `public` FIRST
# so auth tables never get shadowed into gold by create_all.
# See dbt_project/macros/publish_public_serving.sql.
# ---------------------------------------------------------------------------
DB_SCHEMA = os.getenv("API_DB_SCHEMA", "public").strip() or "public"
#: search_path for raw DATA reads (asyncpg pools): data schema first, public fallback.
DATA_SEARCH_PATH = DB_SCHEMA if DB_SCHEMA == "public" else f"{DB_SCHEMA}, public"
#: search_path for the ORM/auth engine: public FIRST so operational tables stay in public.
_ORM_SEARCH_PATH = "public" if DB_SCHEMA == "public" else f"public, {DB_SCHEMA}"

# Create engine
if "sqlite" in DATABASE_URL:
    # SQLite needs special handling for concurrent access
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        # Pin the ORM/auth search_path (public-first) so Base.metadata.create_all
        # always targets public even when a private instance serves data from gold.
        connect_args={"options": f"-csearch_path={_ORM_SEARCH_PATH}"},
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)
    print(f"✅ Database initialized at: {DATABASE_URL}")


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency for FastAPI
    
    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
