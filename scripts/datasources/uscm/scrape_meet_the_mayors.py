#!/usr/bin/env python3
"""
Backward-compatible entrypoint for ``download_uscm_mayors.py``.

Prefer running ``download_uscm_mayors.py`` directly.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "download_uscm_mayors.py"
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")
