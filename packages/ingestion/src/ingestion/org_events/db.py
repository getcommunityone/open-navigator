"""Warehouse access for organization events (#1347): the local warehouse only, never Neon."""

from __future__ import annotations

import os

WEBSITE_TABLE = "bronze.bronze_organization_website"
EVENT_TABLE = "bronze.bronze_organization_event"

DDL = f"""
create table if not exists {WEBSITE_TABLE} (
    ein             text primary key,
    website_url     text,
    source_url      text,
    tax_year        integer,
    fetched_at      timestamptz not null default now(),
    crawl_status    text,
    crawled_at      timestamptz,
    events_found    integer
);
create table if not exists {EVENT_TABLE} (
    event_key        text primary key,
    ein              text not null,
    title            text not null,
    start_at         timestamptz,
    start_date       date not null,
    end_at           timestamptz,
    location         text,
    event_url        text,
    source_page_url  text not null,
    source_format    text not null,
    fetched_at       timestamptz not null default now()
);
create index if not exists bronze_organization_event_ein_idx on {EVENT_TABLE} (ein);
"""


def dsn(explicit: str | None = None) -> str:
    """``--dsn``, else the local warehouse (localhost:5433). A Neon URL is refused: loads target dev only."""
    url = (explicit or "").strip() or (
        f"postgresql://postgres:{os.environ.get('POSTGRES_PASSWORD') or 'password'}@localhost:5433/open_navigator"
    )
    if "neon.tech" in url:
        raise SystemExit("Refusing to write organization events to Neon; use the local warehouse.")
    return url
