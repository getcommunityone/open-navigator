"""Context-managed sessions: explicit transactions, commit on success, rollback on error."""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from .engine import get_async_engine, get_sync_engine

_sync_factory: sessionmaker | None = None
_async_factory: async_sessionmaker | None = None


def _sync_sf() -> sessionmaker:
    global _sync_factory
    if _sync_factory is None:
        _sync_factory = sessionmaker(bind=get_sync_engine(), autoflush=False, expire_on_commit=False)
    return _sync_factory


def _async_sf() -> async_sessionmaker:
    global _async_factory
    if _async_factory is None:
        _async_factory = async_sessionmaker(bind=get_async_engine(), expire_on_commit=False)
    return _async_factory


@contextmanager
def sync_session() -> Iterator[Session]:
    """Sync transactional session for FastAPI routes and sync scripts."""
    session = _sync_sf()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        logger.bind(component="db").exception("sync_session_rollback")
        raise
    finally:
        session.close()


@asynccontextmanager
async def async_session() -> AsyncIterator[AsyncSession]:
    """Async transactional session for ingestion pipelines."""
    session = _async_sf()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        logger.bind(component="db").exception("async_session_rollback")
        raise
    finally:
        await session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency. Drop-in replacement for api.database.get_db."""
    with sync_session() as s:
        yield s
