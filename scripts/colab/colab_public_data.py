"""
Colab judges: fetch hackathon pipeline data without mounting personal Google Drive.

Downloads a **public** Drive folder (Anyone with the link → Viewer) into
``/content/hackathon_pipeline`` using ``gdown``. Maintainers publish the demo
tree and set :data:`PUBLIC_HACKATHON_DRIVE_FOLDER_ID` in
``scripts/utils/gdrive_paths.py`` (or env ``GOVERNANCE_PUBLIC_DRIVE_FOLDER_ID``).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from scripts.utils.gdrive_paths import (
    HACKATHON_SCRAPED_MEETINGS_INVENTORY_REL,
    default_colab_hackathon_pipeline_root,
    default_hackathon_pipeline_root_in_repo,
    default_scraped_meetings_data_cache,
    public_hackathon_drive_folder_id,
    public_hackathon_drive_zip_file_id,
)

_MARKER_NAME = ".colab_public_data_manifest.json"
_DRIVE_ID_RE = re.compile(r"[-\w]{25,}")


def _ensure_gdown() -> None:
    try:
        import gdown  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", "gdown>=5.0"],
        )


def _extract_drive_id(value: str) -> str:
    """Accept a bare id or a full ``drive.google.com`` URL."""
    raw = (value or "").strip()
    if not raw:
        return ""
    for pattern in (
        r"/folders/([-\w]+)",
        r"[?&]id=([-\w]+)",
        r"/file/d/([-\w]+)",
    ):
        match = re.search(pattern, raw)
        if match:
            return match.group(1)
    if _DRIVE_ID_RE.fullmatch(raw):
        return raw
    return raw


def _jurisdiction_has_media(jurisdiction_dir: Path) -> bool:
    if not jurisdiction_dir.is_dir():
        return False
    media_suffixes = {
        ".pdf",
        ".mp3",
        ".mp4",
        ".m4a",
        ".wav",
        ".opus",
        ".webm",
        ".m3u8",
    }
    for path in jurisdiction_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in media_suffixes:
            return True
    return False


def pipeline_has_raw_inputs(pipeline_root: Path) -> bool:
    """True when ``01_raw_inputs`` contains at least one hackathon inventory with media."""
    raw = pipeline_root / "01_raw_inputs"
    if not raw.is_dir():
        return False
    for rel in HACKATHON_SCRAPED_MEETINGS_INVENTORY_REL:
        if _jurisdiction_has_media(raw / rel):
            return True
    # Any jurisdiction tree with media (custom uploads)
    for state_dir in raw.iterdir():
        if not state_dir.is_dir() or state_dir.name.startswith("."):
            continue
        for jtype in state_dir.iterdir():
            if not jtype.is_dir():
                continue
            for jur in jtype.iterdir():
                if jur.is_dir() and _jurisdiction_has_media(jur):
                    return True
    return False


def _read_manifest(pipeline_root: Path) -> dict:
    path = pipeline_root / _MARKER_NAME
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_manifest(pipeline_root: Path, *, source: str, source_id: str) -> None:
    pipeline_root.mkdir(parents=True, exist_ok=True)
    payload = {"source": source, "source_id": source_id}
    (pipeline_root / _MARKER_NAME).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _manifest_matches(pipeline_root: Path, *, source: str, source_id: str) -> bool:
    manifest = _read_manifest(pipeline_root)
    return manifest.get("source") == source and manifest.get("source_id") == source_id


def resolve_pipeline_root_under_download(staging: Path) -> Path:
    """
    Find ``…/2026_Gemma_4_Good`` (or any dir with ``01_raw_inputs``) under a gdown tree.
    """
    staging = staging.resolve()
    named = staging / "2026_Gemma_4_Good"
    if (named / "01_raw_inputs").is_dir():
        return named
    community = (
        staging / "CommunityOne" / "hackathons" / "2026_Gemma_4_Good"
    )
    if (community / "01_raw_inputs").is_dir():
        return community
    if (staging / "01_raw_inputs").is_dir():
        return staging
    for candidate in staging.rglob("01_raw_inputs"):
        if candidate.is_dir():
            parent = candidate.parent
            if parent.name == "2026_Gemma_4_Good" or parent.parent.name == "hackathons":
                return parent
    return staging


def _install_tree(src_root: Path, dest_root: Path) -> None:
    """Copy or merge ``src_root`` into ``dest_root`` (pipeline hackathon layout)."""
    dest_root.mkdir(parents=True, exist_ok=True)
    for item in src_root.iterdir():
        if item.name.startswith("."):
            continue
        target = dest_root / item.name
        if item.is_dir():
            if target.exists():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copytree(item, target)
        elif item.is_file():
            shutil.copy2(item, target)


def _download_public_folder(folder_id: str, staging: Path) -> Path:
    _ensure_gdown()
    import gdown

    staging.mkdir(parents=True, exist_ok=True)
    print(
        f"Downloading public hackathon data from Google Drive folder {folder_id} …\n"
        "(Anyone-with-link; no personal Drive mount required.)"
    )
    gdown.download_folder(
        id=folder_id,
        output=str(staging),
        quiet=False,
        remaining_ok=True,
    )
    return resolve_pipeline_root_under_download(staging)


def _download_public_zip(file_id: str, staging: Path) -> Path:
    _ensure_gdown()
    import gdown

    staging.mkdir(parents=True, exist_ok=True)
    archive = staging / "hackathon_data.zip"
    print(
        f"Downloading public hackathon zip from Google Drive file {file_id} …\n"
        "(Anyone-with-link; no personal Drive mount required.)"
    )
    gdown.download(id=file_id, output=str(archive), quiet=False)
    extract_dir = staging / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(str(archive), str(extract_dir))
    return resolve_pipeline_root_under_download(extract_dir)


def _seed_from_repo(repo: Path, pipeline_root: Path) -> bool:
    """Copy hackathon inventory from repo ``data/cache/scraped_meetings`` when present."""
    cache = default_scraped_meetings_data_cache()
    if repo.resolve() != cache.resolve().parents[2]:
        # cache path is repo-relative; only seed when repo matches
        cache = repo / "data" / "cache" / "scraped_meetings"
    if not cache.is_dir():
        return False
    raw = pipeline_root / "01_raw_inputs"
    raw.mkdir(parents=True, exist_ok=True)
    copied_any = False
    for rel in HACKATHON_SCRAPED_MEETINGS_INVENTORY_REL:
        src = cache / rel
        if not src.is_dir():
            continue
        dest = raw / rel
        if dest.exists():
            copied_any = True
            continue
        shutil.copytree(src, dest)
        copied_any = True
    return copied_any and pipeline_has_raw_inputs(pipeline_root)


def _seed_from_repo_hackathon_layout(repo: Path, pipeline_root: Path) -> bool:
    src = default_hackathon_pipeline_root_in_repo()
    if repo.resolve() != src.resolve().parents[3]:
        src = repo / "data" / "hackathons" / "2026_Gemma_4_Good"
    if not (src / "01_raw_inputs").is_dir():
        return False
    _install_tree(src, pipeline_root)
    return pipeline_has_raw_inputs(pipeline_root)


def _ensure_pipeline_layout(pipeline_root: Path) -> None:
    from scripts.utils.gdrive_paths import GovernancePipelinePaths

    paths = GovernancePipelinePaths(
        root=pipeline_root,
        raw_inputs=pipeline_root / "01_raw_inputs",
        meeting_data_by_jurisdiction_id=pipeline_root
        / "02_reference_data"
        / "meeting_data_by_jurisdiction_id",
        contacts_by_jurisdiction_id=pipeline_root
        / "02_reference_data"
        / "contacts_by_jurisdiction_id",
        transcripts=pipeline_root / "03_processed_outputs" / "01_transcripts",
        gemma_json=pipeline_root / "03_processed_outputs" / "02_gemma_json",
        human_summaries=pipeline_root
        / "03_processed_outputs"
        / "03_human_summaries",
    )
    paths.ensure_dirs()
    raw = pipeline_root / "01_raw_inputs"
    raw.mkdir(parents=True, exist_ok=True)


def ensure_colab_hackathon_data(repo: Path) -> Path:
    """
    Ensure ``/content/hackathon_pipeline`` has ``01_raw_inputs`` with demo media.

    Idempotent per session when the manifest matches the configured public source.
    """
    pipeline_root = default_colab_hackathon_pipeline_root()
    explicit = (os.environ.get("GOVERNANCE_PIPELINE_DATA_ROOT") or "").strip()
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if pipeline_has_raw_inputs(root):
            return root

    folder_id = _extract_drive_id(
        (os.environ.get("GOVERNANCE_PUBLIC_DRIVE_FOLDER_ID") or "").strip()
        or public_hackathon_drive_folder_id()
    )
    zip_id = _extract_drive_id(
        (os.environ.get("GOVERNANCE_PUBLIC_DRIVE_ZIP_FILE_ID") or "").strip()
        or public_hackathon_drive_zip_file_id()
    )

    if pipeline_has_raw_inputs(pipeline_root):
        if folder_id and _manifest_matches(
            pipeline_root, source="drive_folder", source_id=folder_id
        ):
            print(f"Hackathon data already on disk: {pipeline_root}")
            return pipeline_root
        if zip_id and _manifest_matches(
            pipeline_root, source="drive_zip", source_id=zip_id
        ):
            print(f"Hackathon data already on disk: {pipeline_root}")
            return pipeline_root
        if not folder_id and not zip_id:
            print(f"Hackathon data already on disk: {pipeline_root}")
            return pipeline_root

    _ensure_pipeline_layout(pipeline_root)

    if _seed_from_repo_hackathon_layout(repo, pipeline_root):
        _write_manifest(pipeline_root, source="repo_hackathon", source_id=str(repo))
        print(f"Seeded hackathon data from repo layout → {pipeline_root}")
        return pipeline_root

    if _seed_from_repo(repo, pipeline_root):
        _write_manifest(pipeline_root, source="repo_cache", source_id=str(repo))
        print(f"Seeded hackathon raw inputs from repo cache → {pipeline_root}")
        return pipeline_root

    staging = Path("/content/_hackathon_public_download")
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)

    if folder_id:
        resolved = _download_public_folder(folder_id, staging)
        _install_tree(resolved, pipeline_root)
        _write_manifest(pipeline_root, source="drive_folder", source_id=folder_id)
        shutil.rmtree(staging, ignore_errors=True)
        if pipeline_has_raw_inputs(pipeline_root):
            print(f"Public Drive folder → {pipeline_root}")
            return pipeline_root

    if zip_id:
        resolved = _download_public_zip(zip_id, staging)
        _install_tree(resolved, pipeline_root)
        _write_manifest(pipeline_root, source="drive_zip", source_id=zip_id)
        shutil.rmtree(staging, ignore_errors=True)
        if pipeline_has_raw_inputs(pipeline_root):
            print(f"Public Drive zip → {pipeline_root}")
            return pipeline_root

    raise RuntimeError(
        "Could not load hackathon demo data on Colab.\n\n"
        "Judges: this notebook does **not** mount your personal Google Drive.\n"
        "It downloads a **public** Drive folder into /content/hackathon_pipeline.\n\n"
        "Maintainers must publish the demo tree (Share → Anyone with the link → Viewer)\n"
        "and set one of:\n"
        "  • GOVERNANCE_PUBLIC_DRIVE_FOLDER_ID  (folder id or share URL)\n"
        "  • GOVERNANCE_PUBLIC_DRIVE_ZIP_FILE_ID  (single .zip of 2026_Gemma_4_Good)\n"
        "in scripts/utils/gdrive_paths.py or Colab env before judging.\n\n"
        f"Configured folder id: {folder_id or '(not set)'}\n"
        f"Configured zip id:     {zip_id or '(not set)'}\n"
    )


def colab_uses_personal_drive() -> bool:
    return os.environ.get("GOVERNANCE_COLAB_MOUNT_PERSONAL_DRIVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
