"""
Google Drive path helpers — same env contract as ``scripts/utils/log_sync.py`` and
``export_bronze_to_json.py`` (``LOG_GDRIVE_MOUNT``).

Use **one** mount variable for logs, wikidata exports, and meetings downloads; override only when
you need a different meetings folder via ``SCRAPED_MEETINGS_ROOT`` or ``SCRAPED_MEETINGS_RELATIVE``.
"""
from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_LOG_GDRIVE_MOUNT = "/mnt/g/My Drive"


def gdrive_mount_path() -> Path:
    """Mounted Google Drive root (default ``/mnt/g/My Drive``)."""
    return Path(os.getenv("LOG_GDRIVE_MOUNT", _DEFAULT_LOG_GDRIVE_MOUNT)).expanduser()


def scraped_meetings_relative_parts() -> tuple[str, ...]:
    """Path segments under the mount for meeting artifacts (default ``CommunityOne/scraped_meetings``)."""
    raw = (os.getenv("SCRAPED_MEETINGS_RELATIVE") or "CommunityOne/scraped_meetings").strip()
    if not raw:
        raw = "CommunityOne/scraped_meetings"
    norm = raw.replace("\\", "/").strip("/")
    return tuple(p for p in norm.split("/") if p)


def resolve_scraped_meetings_output_root() -> Path:
    """
    Resolve where meeting PDFs should be stored.

    - If ``SCRAPED_MEETINGS_ROOT`` is set → that path (full override).
    - Else if ``LOG_GDRIVE_MOUNT`` exists as a directory → ``LOG_GDRIVE_MOUNT`` / ``SCRAPED_MEETINGS_RELATIVE``.
    - Else → ``~/CommunityOne/scraped_meetings``.
    """
    explicit = (os.getenv("SCRAPED_MEETINGS_ROOT") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    mount = gdrive_mount_path()
    dest = mount.joinpath(*scraped_meetings_relative_parts())
    if mount.is_dir():
        return dest
    return Path.home() / "CommunityOne" / "scraped_meetings"
