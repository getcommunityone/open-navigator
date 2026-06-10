"""
Google Drive path / pipeline-layout helpers (``core_lib.gdrive_paths``).

Shared across the workspace — primary consumers are ``llm.governance.*`` (the Gemma
hackathon governance pipeline) and ``scrapers.wikidata.export_bronze_to_json``, plus the
legacy ``scripts/utils/log_sync.py`` and ``scripts/discovery/*`` loaders.

- ``LOG_GDRIVE_MOUNT`` / ``gdrive_mount_path()`` — configured path (may not exist yet).
  ``resolved_gdrive_mount_path()`` — when the configured path is missing, may pick another
  ``/mnt/<letter>/My Drive`` or ``/mnt/c/Users/*/Google Drive/My Drive`` (Drive layout varies).
- ``resolve_scraped_meetings_output_root()`` — **meetings scraper** default is the repo cache
  (``data/cache/scraped_meetings``), same family as ``data/cache/wikidata``. Override with
  ``SCRAPED_MEETINGS_ROOT`` (e.g. a mounted Drive path) when you want artifacts outside the repo.
- ``scraped_meetings_gdrive_mirror_root()`` — default Drive mirror folder
  ``CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs`` under ``resolved_gdrive_mount_path()``
  (see ``packages/llm/src/llm/governance/01_copy_scraped_meetings_cache_to_gdrive.py``). Override with
  ``SCRAPED_MEETINGS_GDRIVE_MIRROR`` (absolute path to the *mirror root* folder).
- ``GovernancePipelinePaths`` — same numbered folder layout as
  ``packages/llm/src/llm/governance/02_init_drive_layout.ipynb`` (ingestion / reference data / processed).
  On **Google Colab**, set ``GOVERNANCE_PIPELINE_DATA_ROOT`` to e.g.
  ``/content/drive/MyDrive/CommunityOne/hackathons/2026_Gemma_4_Good`` before importing.
"""
from __future__ import annotations

import glob
import os
import string
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_LOG_GDRIVE_MOUNT = "/mnt/g/My Drive"

# ``packages/core-lib/src/core_lib/gdrive_paths.py`` → repo root is four parents up
# (``core_lib`` → ``src`` → ``core-lib`` → ``packages`` → repo root).
_REPO_ROOT = Path(__file__).resolve().parents[4]


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
# ``packages/llm/src/llm/governance/01_copy_scraped_meetings_cache_to_gdrive.py`` (default scope; pass ``--all-cache`` for full tree).
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


# Hackathon pipeline root on Drive (``01_raw_inputs``, ``03_processed_outputs``, …).
HACKATHON_PIPELINE_ROOT_REL = Path("CommunityOne") / "hackathons" / "2026_Gemma_4_Good"

# Colab judges: public Drive folder (Anyone with the link → Viewer). No personal mount.
# Set the folder id after publishing ``2026_Gemma_4_Good`` (or override via env).
_DEFAULT_PUBLIC_HACKATHON_DRIVE_FOLDER_ID = ""
_DEFAULT_PUBLIC_HACKATHON_DRIVE_ZIP_FILE_ID = ""

# Writable Colab runtime root (outputs + downloaded inputs survive the session).
DEFAULT_COLAB_HACKATHON_PIPELINE_ROOT = Path("/content/hackathon_pipeline")


def default_colab_hackathon_pipeline_root() -> Path:
    return DEFAULT_COLAB_HACKATHON_PIPELINE_ROOT


def public_hackathon_drive_folder_id() -> str:
    return (
        os.getenv("GOVERNANCE_PUBLIC_DRIVE_FOLDER_ID", _DEFAULT_PUBLIC_HACKATHON_DRIVE_FOLDER_ID)
        or ""
    ).strip()


def public_hackathon_drive_zip_file_id() -> str:
    return (
        os.getenv("GOVERNANCE_PUBLIC_DRIVE_ZIP_FILE_ID", _DEFAULT_PUBLIC_HACKATHON_DRIVE_ZIP_FILE_ID)
        or ""
    ).strip()

# Default mirror location under ``My Drive`` when ``SCRAPED_MEETINGS_GDRIVE_MIRROR`` is unset.
SCRAPED_MEETINGS_GDRIVE_REL = HACKATHON_PIPELINE_ROOT_REL / "01_raw_inputs"


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


def default_hackathon_pipeline_root_in_repo() -> Path:
    """Local Jupyter/WSL default: ``<repo>/data/hackathons/2026_Gemma_4_Good``."""
    return _REPO_ROOT / "data" / "hackathons" / "2026_Gemma_4_Good"


def resolve_governance_pipeline_data_root() -> Path:
    """
    Root folder for governance hackathon / Gemma pipeline data on Drive (or any disk).

    Resolution order:

    1. ``GOVERNANCE_PIPELINE_DATA_ROOT`` — absolute path (use this on **Colab**:
       ``/content/drive/MyDrive/CommunityOne/hackathons/2026_Gemma_4_Good``).
    2. ``resolved_gdrive_mount_path()`` / ``GOVERNANCE_PIPELINE_GDRIVE_BASE`` — default
       ``CommunityOne/hackathons/2026_Gemma_4_Good`` (WSL + Google Drive Desktop).
    3. Repo checkout: ``data/hackathons/2026_Gemma_4_Good`` when no Drive mount.
    """
    explicit = (os.getenv("GOVERNANCE_PIPELINE_DATA_ROOT") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    rel = os.getenv(
        "GOVERNANCE_PIPELINE_GDRIVE_BASE",
        HACKATHON_PIPELINE_ROOT_REL.as_posix(),
    ).strip()
    mounted = resolved_gdrive_mount_path() / rel
    if mounted.is_dir():
        return mounted
    return default_hackathon_pipeline_root_in_repo()


def resolve_governance_raw_inputs_root(pipeline_root: Path | None = None) -> Path:
    """
    Folder walked by Gatekeeper / §5 inventory (``AL/county/county_…`` layout).

    1. ``GOVERNANCE_RAW_INPUTS_ROOT`` if set
    2. ``<pipeline_root>/01_raw_inputs`` when it exists
    3. ``<repo>/data/cache/scraped_meetings`` only when ``GOVERNANCE_PIPELINE_DATA_ROOT`` is
       **not** set and ``GOVERNANCE_USE_SCRAPED_CACHE_FALLBACK=1`` (opt-in; full cache is huge).
    4. else ``<pipeline_root>/01_raw_inputs`` (caller may raise if missing)
    """
    explicit = (os.getenv("GOVERNANCE_RAW_INPUTS_ROOT") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    root = Path(pipeline_root) if pipeline_root else resolve_governance_pipeline_data_root()
    raw = root / "01_raw_inputs"
    if raw.is_dir():
        return raw
    pipeline_explicit = (os.getenv("GOVERNANCE_PIPELINE_DATA_ROOT") or "").strip()
    allow_cache = os.environ.get("GOVERNANCE_USE_SCRAPED_CACHE_FALLBACK", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not pipeline_explicit and allow_cache:
        cache = default_scraped_meetings_data_cache()
        if cache.is_dir():
            return cache
    return raw


@dataclass(frozen=True)
class GovernancePipelinePaths:
    """Mirror ``packages/llm/src/llm/governance/02_init_drive_layout.ipynb`` directory tree."""

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
