#!/usr/bin/env python3
"""Thin CLI shim for the Census govsstatefin variables codebook pipeline.

The real implementation lives at
``packages/ingestion/src/ingestion/census/govsstatefin_variables.py`` under
the ``DataSourcePipeline`` contract — async + pydantic-validated rows +
timestamped snapshots in ``data/cache/census/govsstatefin_variables/`` +
unit tests at
``packages/ingestion/tests/test_census_govsstatefin_variables_pipeline.py``.

Sibling to ``download_census_acs_data.py`` etc. so the census/ folder stays
the single discoverable home for "how do I refresh a Census-derived dataset?"
New invocations should prefer::

    python -m ingestion.census.govsstatefin_variables

Both entry points accept the same flags (``--dataset``, ``--url``,
``--no-fetch``, ``--snapshot``, ``--truncate``, ``--limit``).
"""
from __future__ import annotations

from ingestion.census.govsstatefin_variables import main

if __name__ == "__main__":
    main()
