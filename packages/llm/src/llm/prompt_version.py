"""A prompt's version, derived from its content.

``bronze_events_analysis_ai.prompt_version`` was the constant ``"v1.0"`` on every
row, however often the prompt changed, so no row showed which wording produced it.
A version is now ``<prompt name>@<first 12 hex of the prompt's SHA-256>``: it changes
whenever the prompt text does and fits the column's 50 characters.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Optional

UNRECORDED = "unrecorded"
MAX_LEN = 50


def prompt_sha256(text: str | bytes) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()


def prompt_file_sha256(path: Path) -> Optional[str]:
    try:
        return prompt_sha256(Path(path).read_bytes())
    except OSError:
        return None


def prompt_version_label(name: Optional[str], sha256: Optional[str]) -> Optional[str]:
    """``name@sha12``; ``name@unrecorded`` when the hash wasn't recorded; ``None`` with neither.

    Analyses saved before the hash was recorded get ``@unrecorded``, never a
    version they didn't have.
    """
    stem = (name or "").strip() or None
    sha = (sha256 or "").strip().lower() or None
    if sha:
        return f"{stem or 'prompt'}@{sha[:12]}"[:MAX_LEN]
    if stem:
        return f"{stem}@{UNRECORDED}"[:MAX_LEN]
    return None


def prompt_version_from_meta(meta: Optional[Mapping[str, Any]]) -> Optional[str]:
    """The version for an analysis from its ``*.meta.json`` (``prompt_name`` / ``prompt_file``, ``prompt_sha256``)."""
    m = meta or {}
    name = m.get("prompt_name") or (Path(str(m["prompt_file"])).stem if m.get("prompt_file") else None)
    return prompt_version_label(name, m.get("prompt_sha256"))
