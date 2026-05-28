#!/usr/bin/env python3
"""Thin CLI shim for the BLS CPI ingestion pipeline.

The real implementation lives at ``packages/ingestion/src/ingestion/bls/cpi.py``
under the ``DataSourcePipeline`` contract — async + pydantic-validated rows +
``data/cache/bls/*.json`` FETCH/LAND split + a unit test at
``packages/ingestion/tests/test_bls_cpi_pipeline.py``.

This shim is kept for back-compat with the path baked into docs / runbooks
that landed in PR #34. New invocations should prefer::

    python -m ingestion.bls.cpi

Both entry points accept the same flags (``--series``, ``--start-year``,
``--end-year``, ``--refresh``, ``--no-fetch``, ``--truncate``, ``--limit``).
"""
from __future__ import annotations

from ingestion.bls.cpi import main

if __name__ == "__main__":
    main()
