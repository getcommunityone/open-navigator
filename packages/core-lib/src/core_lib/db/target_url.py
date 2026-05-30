"""Resolve the target Postgres URL for Open Navigator loaders.

Priority (first non-empty wins):
    NEON_DATABASE_URL_DEV        — Neon dev branch (default for discovery / loaders)
    OPEN_NAVIGATOR_DATABASE_URL  — explicit override (any postgres host)
    NEON_DATABASE_URL            — Neon prod-like
    local default                — docker-style local open_navigator
"""

from __future__ import annotations

import os


def resolve_target_database_url() -> str:
    neon_dev = (os.getenv("NEON_DATABASE_URL_DEV") or "").strip()
    if neon_dev:
        return neon_dev
    explicit = (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
    if explicit:
        return explicit
    neon = (os.getenv("NEON_DATABASE_URL") or "").strip()
    if neon:
        return neon

    pwd = os.getenv("POSTGRES_PASSWORD", "password")
    return "postgresql://postgres:" + pwd + "@localhost:5433/open_navigator"
