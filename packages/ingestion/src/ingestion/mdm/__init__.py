"""Master Data Management — entity resolution over the conformed MDM pools.

Layer 3 of the pipeline described in web_docs/docs/dbt/entity-resolution-mdm.md.
dbt builds the conformed inputs (``intermediate.int_addresses__unioned`` and
``intermediate.int_persons__unioned``); this package runs Splink against them to
predict matches and cluster each occurrence into a master entity, then writes the
clusters back to ``bronze`` for dbt to serve.

CLI:
    python -m ingestion.mdm address          # resolve int_addresses__unioned
    python -m ingestion.mdm person --dry-run # validate config without compute

``ingestion.mdm.db`` is importable without splink installed; the linker/settings
helpers import splink lazily on first access.
"""

from __future__ import annotations

from typing import Any

__all__ = ["address_settings", "person_settings", "run_linker"]


def __getattr__(name: str) -> Any:  # PEP 562 lazy re-exports (avoid importing splink at package init)
    if name == "run_linker":
        from ingestion.mdm.linker import run_linker

        return run_linker
    if name in ("address_settings", "person_settings"):
        from ingestion.mdm import settings

        return getattr(settings, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
