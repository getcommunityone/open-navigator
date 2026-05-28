#!/usr/bin/env python3
"""Thin CLI shim for the TPC Government Finance ingestion pipeline.

The real implementation lives at
``packages/ingestion/src/ingestion/tpc/finance.py`` under the
``DataSourcePipeline`` contract (async + pydantic-validated rows +
``data/cache/tpc/`` FETCH/LAND split + unit tests at
``packages/ingestion/tests/test_tpc_finance_pipeline.py``).

This shim is provided for discoverability — every other source under
``scripts/datasources/`` has a sibling shim, so operators looking here for
"how do I load TPC?" land on a working entry point. New invocations should
prefer::

    python -m ingestion.tpc.finance

Both entry points accept the same flags (``--file``, ``--gov-type``,
``--fetch``, ``--file-id``, ``--refresh``, ``--truncate``, ``--limit``).
"""
from __future__ import annotations

from ingestion.tpc.finance import main

if __name__ == "__main__":
    main()
