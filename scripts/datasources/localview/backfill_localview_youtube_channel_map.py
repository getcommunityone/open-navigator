#!/usr/bin/env python3
"""Thin CLI shim for the LocalView YouTube video -> channel mapping pipeline.

The real implementation lives at
``packages/ingestion/src/ingestion/localview/channel_map.py`` under the
``DataSourcePipeline`` contract (async + pydantic-validated rows +
unit tests at ``packages/ingestion/tests/test_localview_channel_map_pipeline.py``).

New invocations should prefer::

    python -m ingestion.localview.channel_map

Both entry points accept the same flags (``--file``, ``--limit``,
``--truncate``, ``--drop-bronze-channel-id``, ``--dry-run``).
"""
from __future__ import annotations

from ingestion.localview.channel_map import (  # noqa: F401
    LocalviewVideoChannelRow,
    LocalviewVideoChannelsPipeline,
    build_parser,
    extract_parquet_mappings,
    find_parquet_files,
    main,
)

if __name__ == "__main__":
    main()
