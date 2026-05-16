"""
Path helpers shared with ``scripts/utils/log_sync.py`` and ``export_bronze_to_json.py``.

- ``LOG_GDRIVE_MOUNT`` / ``gdrive_mount_path()`` — configured path (may not exist yet).
  ``resolved_gdrive_mount_path()`` — when the configured path is missing, may pick another
  ``/mnt/<letter>/My Drive`` or ``/mnt/c/Users/*/Google Drive/My Drive`` (Drive layout varies).
- ``resolve_scraped_meetings_output_root()`` — **meetings scraper** default is the repo cache
  (``data/cache/scraped_meetings``), same family as ``data/cache/wikidata``. Override with
  ``SCRAPED_MEETINGS_ROOT`` (e.g. a mounted Drive path) when you want artifacts outside the repo.
- ``scraped_meetings_gdrive_mirror_root()`` — default Drive mirror folder
  ``CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs`` under ``resolved_gdrive_mount_path()``
  (see ``scripts/colab/01_copy_scraped_meetings_cache_to_gdrive.py``). Override with
  ``SCRAPED_MEETINGS_GDRIVE_MIRROR`` (absolute path to the *mirror root* folder).
- ``GovernancePipelinePaths`` — same numbered folder layout as
  ``scripts/colab/02_init_drive_layout.ipynb`` (ingestion / reference data / processed).
  On **Google Colab**, set ``GOVERNANCE_PIPELINE_DATA_ROOT`` to e.g.
  ``/content/drive/MyDrive/CommunityOne/governance_pipeline_data`` before importing.
"""
from __future__ import annotations

import glob
import os
import string
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_LOG_GDRIVE_MOUNT = "/mnt/g/My Drive"

# ``scripts/utils/gdrive_paths.py`` → repo root is two parents up from ``scripts/``.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def gdrive_mount_path() -> Path:
    """Mounted Google Drive root (default ``/mnt/g/My Drive``)."""
    return Path(os.getenv("LOG_GDRIVE_MOUNT", _DEFAULT_LOG_GDRIVE_MOUNT)).expanduser()


def resolved_gdrive_mount_path() -> Path:
    """
    ``My Drive`` path for WSL when using Google Drive for Desktop.

    Returns ``gdrive_mount_path()`` when that path exists. Otherwise, if the user did **not**
    set ``LOG_GDRIVE_MOUNT`` to a **non-default** path, tries (in order): default ``/mnt/g/My Drive``,
    any ``/mnt/<letter>/My Drive``, then ``/mnt/c/Users/*/Google Drive/My Drive``. Scripts cannot
    mount Drive; this only discovers an already-mounted path.
    """
    configured = gdrive_mount_path()
    if configured.is_dir():
        return configured

    env_raw = (os.getenv("LOG_GDRIVE_MOUNT") or "").strip()
    default_norm = os.path.normpath(os.path.expanduser(_DEFAULT_LOG_GDRIVE_MOUNT))
    if env_raw and os.path.normpath(os.path.expanduser(env_raw)) != default_norm:
        return configured

    default = Path(_DEFAULT_LOG_GDRIVE_MOUNT)
    if default.is_dir():
        return default
    for letter in string.ascii_lowercase:
        candidate = Path(f"/mnt/{letter}/My Drive")
        if candidate.is_dir():
            return candidate
    for pattern in (
        "/mnt/c/Users/*/Google Drive/My Drive",
        "/mnt/d/Users/*/Google Drive/My Drive",
    ):
        for match in sorted(glob.glob(pattern)):
            found = Path(match)
            if found.is_dir():
                return found
    return configured


def default_scraped_meetings_data_cache() -> Path:
    """Default meetings artifact root: ``<repo>/data/cache/scraped_meetings`` (gitignored ``data/``)."""
    return _REPO_ROOT / "data" / "cache" / "scraped_meetings"


# 2026 Gemma hackathon Colab sync set (Tuscaloosa + Big Timber county/city). Used by
# ``scripts/colab/01_copy_scraped_meetings_cache_to_gdrive.py`` (default scope; pass ``--all-cache`` for full tree).
HACKATHON_SCRAPED_MEETINGS_INVENTORY_REL: tuple[str, ...] = (
    "AL/county/county_01125",
    "MT/county/county_30097",
    "AL/municipality/municipality_0177256",
    "MT/municipality/municipality_3006475",
)


def hackathon_scraped_meetings_inventory_dirs(
    src_root: Path | None = None,
) -> tuple[Path, ...]:
    """Absolute paths for each hackathon inventory folder under ``src_root`` (default: repo cache)."""
    root = (
        src_root.expanduser().resolve()
        if src_root is not None
        else resolve_scraped_meetings_output_root()
    )
    return tuple(root / rel for rel in HACKATHON_SCRAPED_MEETINGS_INVENTORY_REL)


# Default mirror location under ``My Drive`` when ``SCRAPED_MEETINGS_GDRIVE_MIRROR`` is unset.
SCRAPED_MEETINGS_GDRIVE_REL = Path("CommunityOne") / "hackathons" / "2026_Gemma_4_Good" / "01_raw_inputs"


def scraped_meetings_gdrive_mirror_root() -> Path:
    """
    Default Google Drive mirror for scraped meetings (under the mounted Drive root).

    Resolves to ``<resolved My Drive>/CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs``.

    Override with ``SCRAPED_MEETINGS_GDRIVE_MIRROR`` (absolute path to the *mirror root* folder).
    """
    explicit = (os.getenv("SCRAPED_MEETINGS_GDRIVE_MIRROR") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return resolved_gdrive_mount_path() / SCRAPED_MEETINGS_GDRIVE_REL


def scraped_meetings_gdrive_rclone_remote_subpath() -> str:
    """Path under the rclone remote root (no ``remote:`` prefix), POSIX ``/`` separators."""
    return SCRAPED_MEETINGS_GDRIVE_REL.as_posix()


def scraped_meetings_root_resolution_note() -> str:
    """Which env branch :pyfunc:`resolve_scraped_meetings_output_root` used (for logs / manifests)."""
    explicit = (os.getenv("SCRAPED_MEETINGS_ROOT") or "").strip()
    if explicit:
        return "SCRAPED_MEETINGS_ROOT"
    return "DATA_CACHE (repo data/cache/scraped_meetings/)"


def resolve_scraped_meetings_output_root() -> Path:
    """
    Resolve where meeting PDFs should be stored.

    - If ``SCRAPED_MEETINGS_ROOT`` is set → that path (full override, e.g. Google Drive mount).
    - Else → ``<open-navigator>/data/cache/scraped_meetings`` (with ``{state}/{type}/{id}/…`` under it).
    """
    explicit = (os.getenv("SCRAPED_MEETINGS_ROOT") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return default_scraped_meetings_data_cache()


def resolve_governance_pipeline_data_root() -> Path:
    """
    Root folder for governance hackathon / Gemma pipeline data on Drive (or any disk).

    Resolution order:

    1. ``GOVERNANCE_PIPELINE_DATA_ROOT`` — absolute path (use this on **Colab**:
       ``/content/drive/MyDrive/CommunityOne/governance_pipeline_data``).
    2. ``resolved_gdrive_mount_path()`` / ``GOVERNANCE_PIPELINE_GDRIVE_BASE`` — default base
       ``CommunityOne/governance_pipeline_data`` (WSL + Google Drive Desktop: ``/mnt/g/My Drive/...``).
    """
    explicit = (os.getenv("GOVERNANCE_PIPELINE_DATA_ROOT") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    rel = os.getenv(
        "GOVERNANCE_PIPELINE_GDRIVE_BASE",
        "CommunityOne/governance_pipeline_data",
    ).strip()
    return resolved_gdrive_mount_path() / rel


@dataclass(frozen=True)
class GovernancePipelinePaths:
    """Mirror ``scripts/colab/02_init_drive_layout.ipynb`` directory tree."""

    root: Path
    raw_inputs: Path
    meeting_data_by_jurisdiction_id: Path
    contacts_by_jurisdiction_id: Path
    transcripts: Path
    gemma_json: Path
    human_summaries: Path

    @classmethod
    def resolve(cls) -> GovernancePipelinePaths:
        root = resolve_governance_pipeline_data_root()
        reference = root / "02_reference_data"
        return cls(
            root=root,
            raw_inputs=root / "01_raw_inputs",
            meeting_data_by_jurisdiction_id=reference / "meeting_data_by_jurisdiction_id",
            contacts_by_jurisdiction_id=reference / "contacts_by_jurisdiction_id",
            transcripts=root / "03_processed_outputs" / "01_transcripts",
            gemma_json=root / "03_processed_outputs" / "02_gemma_json",
            human_summaries=root / "03_processed_outputs" / "03_human_summaries",
        )

    def ensure_dirs(self) -> None:
        """Create all pipeline stage directories (idempotent)."""
        for p in (
            self.raw_inputs,
            self.meeting_data_by_jurisdiction_id,
            self.contacts_by_jurisdiction_id,
            self.transcripts,
            self.gemma_json,
            self.human_summaries,
        ):
            p.mkdir(parents=True, exist_ok=True)
