"""
Canonical FEC bulk-data directory for this repo.

Override with env ``FEC_DATA_DIR`` (absolute path recommended).
"""

from __future__ import annotations

import os
from pathlib import Path

from core_lib.paths import repo_root
_REPO_ROOT = repo_root(__file__)
DEFAULT_FEC_DATA_DIR = _REPO_ROOT / "data" / "cache" / "fec_data"


def default_fec_data_dir() -> Path:
    """Resolved base dir: ``$FEC_DATA_DIR`` or ``data/cache/fec_data`` under repo root."""
    override = (os.environ.get("FEC_DATA_DIR") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_FEC_DATA_DIR.resolve()
