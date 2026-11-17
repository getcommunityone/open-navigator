#!/usr/bin/env python3
"""Backward-compatible CLI shim for ``ingestion.jurisdictions.mapping.publish_hf``."""
from __future__ import annotations

import sys

from ingestion.jurisdictions.mapping.publish_hf import (
    DEFAULT_SPLIT,
    ROOT,
    TABLE,
    _dataset_readme,
    _db_url,
    _default_repo_id,
    _fetch_dataframe,
    main,
    publish,
)

__all__ = [
    "DEFAULT_SPLIT",
    "ROOT",
    "TABLE",
    "_dataset_readme",
    "_db_url",
    "_default_repo_id",
    "_fetch_dataframe",
    "main",
    "publish",
]

if __name__ == "__main__":
    sys.exit(main())
