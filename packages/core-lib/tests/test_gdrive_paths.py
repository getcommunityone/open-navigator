"""Unit tests for ``core_lib.gdrive_paths`` (ported from ``scripts/utils/``).

No network and no real Google Drive mount: every path helper is exercised either
through env overrides or against a ``tmp_path`` fake layout. Env vars consumed by the
module are isolated per-test via ``monkeypatch``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core_lib import gdrive_paths as g

# Env vars the module reads; cleared before each test so host config can't leak in.
_ENV_VARS = (
    "LOG_GDRIVE_MOUNT",
    "SCRAPED_MEETINGS_ROOT",
    "SCRAPED_MEETINGS_GDRIVE_MIRROR",
    "GOVERNANCE_PIPELINE_DATA_ROOT",
    "GOVERNANCE_PIPELINE_GDRIVE_BASE",
    "GOVERNANCE_RAW_INPUTS_ROOT",
    "GOVERNANCE_USE_SCRAPED_CACHE_FALLBACK",
    "GOVERNANCE_PUBLIC_DRIVE_FOLDER_ID",
    "GOVERNANCE_PUBLIC_DRIVE_ZIP_FILE_ID",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_module_lives_in_core_lib() -> None:
    """Port landed in core-lib, not scripts/."""
    assert g.__name__ == "core_lib.gdrive_paths"
    assert "packages/core-lib/src/core_lib" in g.__file__.replace("\\", "/")


def test_repo_root_points_at_checkout() -> None:
    """``_REPO_ROOT`` resolves to the repo checkout (the dir containing ``packages/``)."""
    assert (g._REPO_ROOT / "packages" / "core-lib").is_dir()


def test_default_scraped_meetings_data_cache_is_under_repo() -> None:
    cache = g.default_scraped_meetings_data_cache()
    assert cache == g._REPO_ROOT / "data" / "cache" / "scraped_meetings"


def test_gdrive_mount_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    assert g.gdrive_mount_path() == Path("/mnt/g/My Drive")


def test_gdrive_mount_path_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_GDRIVE_MOUNT", "/tmp/fake-drive")
    assert g.gdrive_mount_path() == Path("/tmp/fake-drive")


def test_resolved_gdrive_mount_returns_configured_when_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOG_GDRIVE_MOUNT", str(tmp_path))
    assert g.resolved_gdrive_mount_path() == tmp_path


def test_resolved_gdrive_mount_returns_nondefault_even_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A user-set non-default mount is honored verbatim (no auto-discovery override)."""
    missing = tmp_path / "does-not-exist"
    monkeypatch.setenv("LOG_GDRIVE_MOUNT", str(missing))
    assert g.resolved_gdrive_mount_path() == missing


def test_resolve_scraped_meetings_output_root_default() -> None:
    assert g.resolve_scraped_meetings_output_root() == g.default_scraped_meetings_data_cache()


def test_resolve_scraped_meetings_output_root_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SCRAPED_MEETINGS_ROOT", str(tmp_path))
    assert g.resolve_scraped_meetings_output_root() == tmp_path


def test_scraped_meetings_root_resolution_note() -> None:
    assert g.scraped_meetings_root_resolution_note().startswith("DATA_CACHE")


def test_scraped_meetings_root_resolution_note_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SCRAPED_MEETINGS_ROOT", str(tmp_path))
    assert g.scraped_meetings_root_resolution_note() == "SCRAPED_MEETINGS_ROOT"


def test_hackathon_inventory_dirs_join_under_root(tmp_path: Path) -> None:
    dirs = g.hackathon_scraped_meetings_inventory_dirs(src_root=tmp_path)
    assert len(dirs) == len(g.HACKATHON_SCRAPED_MEETINGS_INVENTORY_REL)
    resolved_root = tmp_path.expanduser().resolve()
    for d, rel in zip(dirs, g.HACKATHON_SCRAPED_MEETINGS_INVENTORY_REL):
        assert d == resolved_root / rel


def test_scraped_meetings_gdrive_mirror_explicit_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SCRAPED_MEETINGS_GDRIVE_MIRROR", str(tmp_path))
    assert g.scraped_meetings_gdrive_mirror_root() == tmp_path


def test_scraped_meetings_gdrive_rclone_subpath_is_posix() -> None:
    sub = g.scraped_meetings_gdrive_rclone_remote_subpath()
    assert sub == "CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs"
    assert "\\" not in sub


def test_resolve_governance_pipeline_data_root_explicit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GOVERNANCE_PIPELINE_DATA_ROOT", str(tmp_path))
    assert g.resolve_governance_pipeline_data_root() == tmp_path


def test_resolve_governance_pipeline_data_root_falls_back_to_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No env + no Drive mount → repo-local hackathon folder."""
    # Force the Drive mount probe to a guaranteed-missing path.
    monkeypatch.setenv("LOG_GDRIVE_MOUNT", "/nonexistent/drive/mount/xyz")
    assert g.resolve_governance_pipeline_data_root() == g.default_hackathon_pipeline_root_in_repo()


def test_resolve_governance_raw_inputs_root_explicit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GOVERNANCE_RAW_INPUTS_ROOT", str(tmp_path))
    assert g.resolve_governance_raw_inputs_root() == tmp_path


def test_resolve_governance_raw_inputs_root_uses_existing_subdir(tmp_path: Path) -> None:
    raw = tmp_path / "01_raw_inputs"
    raw.mkdir()
    assert g.resolve_governance_raw_inputs_root(pipeline_root=tmp_path) == raw


def test_resolve_governance_raw_inputs_root_defaults_to_join_when_missing(
    tmp_path: Path,
) -> None:
    # No 01_raw_inputs on disk and no cache fallback → returns the (missing) join.
    assert g.resolve_governance_raw_inputs_root(pipeline_root=tmp_path) == tmp_path / "01_raw_inputs"


def test_public_drive_ids_default_empty() -> None:
    assert g.public_hackathon_drive_folder_id() == ""
    assert g.public_hackathon_drive_zip_file_id() == ""


def test_public_drive_ids_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_PUBLIC_DRIVE_FOLDER_ID", "  folder123  ")
    monkeypatch.setenv("GOVERNANCE_PUBLIC_DRIVE_ZIP_FILE_ID", "zip456")
    assert g.public_hackathon_drive_folder_id() == "folder123"
    assert g.public_hackathon_drive_zip_file_id() == "zip456"


def test_governance_pipeline_paths_resolve_and_ensure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GOVERNANCE_PIPELINE_DATA_ROOT", str(tmp_path))
    paths = g.GovernancePipelinePaths.resolve()
    assert paths.root == tmp_path
    assert paths.raw_inputs == tmp_path / "01_raw_inputs"
    assert paths.transcripts == tmp_path / "03_processed_outputs" / "01_transcripts"
    assert paths.gemma_json == tmp_path / "03_processed_outputs" / "02_gemma_json"

    paths.ensure_dirs()
    for p in (
        paths.raw_inputs,
        paths.meeting_data_by_jurisdiction_id,
        paths.contacts_by_jurisdiction_id,
        paths.transcripts,
        paths.gemma_json,
        paths.human_summaries,
    ):
        assert p.is_dir()
    # Idempotent.
    paths.ensure_dirs()
