"""Neon (cloud Postgres) hosting: migrate, sync, and stat the deployed warehouse.

This is the Postgres counterpart to :mod:`hosting.huggingface` — it owns the
tooling that loads the published gold data and bronze tables into the Neon
cloud Postgres instance that backs the deployed app, plus the idempotent DDL
and statistics refreshers that keep that instance in shape.

Ported from ``scripts/deployment/neon/``. Each module keeps its own
``if __name__ == "__main__"`` entrypoint, so the loaders run as modules::

    python -m hosting.neon.migrate                 # gold parquet -> Neon
    python -m hosting.neon.migrate_bills           # bills map aggregates -> Neon
    python -m hosting.neon.sync_bronze_tables --all # local bronze -> Neon
    python -m hosting.neon.sync_youtube_to_neon
    python -m hosting.neon.update_stats            # refresh national stats
    python -m hosting.neon.calculate_stats_only
    python -m hosting.neon.regenerate_bills_map
    python -m hosting.neon.ensure_bronze_jurisdictions_cloud --schema-only

Connection targets come from the ``NEON_DATABASE_URL`` /
``NEON_DATABASE_URL_DEV`` environment variables (see each module's docstring).

Public API: :func:`ensure_wikidata_tables`, used by the wikidata hydrators in
``communityone-scrapers`` to guarantee the cloud bronze tables exist.
"""

from __future__ import annotations

from .ensure_bronze_jurisdictions_cloud import ensure_wikidata_tables

__all__ = ["ensure_wikidata_tables"]
