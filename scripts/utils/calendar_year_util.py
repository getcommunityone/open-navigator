"""Normalize calendar / tax / filing year labels to VARCHAR(4)-compatible strings."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Optional

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore


def calendar_year_label(value: Any) -> Optional[str]:
    """Return a four-digit year string, or None if missing or not parseable."""
    if value is None:
        return None
    if pd is not None:
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (datetime, date)):
        return str(value.year)
    if isinstance(value, (int,)) and not isinstance(value, bool):
        s = str(value)
        if len(s) >= 4 and s[:4].isdigit():
            return s[:4]
        if s.isdigit() and len(s) < 4:
            return s.zfill(4)
        return None
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "nat", "<na>"):
        return None
    if len(s) >= 6 and s.isdigit():
        s = s[:4]
    if "." in s:
        try:
            s = str(int(float(s)))
        except (ValueError, OverflowError):
            return None
    if len(s) >= 4 and s[:4].isdigit():
        return s[:4]
    if s.isdigit() and len(s) < 4:
        return s.zfill(4)
    return None
