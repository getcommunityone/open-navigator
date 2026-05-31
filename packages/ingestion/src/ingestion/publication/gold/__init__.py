"""Gold-layer parquet build, split, partition and QA tooling.

Ported from the legacy ``scripts/data/`` tree. These modules build and
maintain the ``data/gold/`` parquet datasets that the FastAPI app serves
and that are published for distribution. Each module is runnable as a
CLI, e.g.::

    python -m ingestion.publication.gold.split_gold_by_state --all
    python -m ingestion.publication.gold.organize_meetings_by_state --states AL,GA

All ``data/gold/...`` paths are resolved relative to the current working
directory, so run these from the repository root.
"""
