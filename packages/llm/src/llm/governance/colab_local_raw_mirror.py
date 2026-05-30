"""
Mirror scoped jurisdiction trees from Google Drive to Colab local disk.

Gatekeeper and demos are much faster on ``/content/…`` than on Drive FUSE.
Call :func:`mirror_inventories_to_local_raw` after inventory is built on Drive;
it copies only jurisdictions in ``INVENTORIES`` when the local tree is missing
or stale (Drive ``_manifest.json`` mtime changed).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from .colab_paths import in_colab
from .colab_timed_steps import timed_step
from .governance_meeting_llm import MeetingInventory, parse_jurisdiction_dir


def local_raw_mirror_enabled() -> bool:
    if not in_colab():
        return False
    return os.environ.get("GOVERNANCE_LOCAL_RAW_MIRROR", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def default_local_raw_root() -> Path:
    raw = os.environ.get("GOVERNANCE_LOCAL_RAW_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path("/content/governance_pipeline_local/01_raw_inputs")


def _is_drive_path(path: Path) -> bool:
    return "/content/drive" in path.resolve().as_posix()


def _jurisdiction_relpath(jurisdiction_root: Path, drive_raw_root: Path) -> Path:
    return jurisdiction_root.resolve().relative_to(drive_raw_root.resolve())


def _mirror_stamp_path(local_jur: Path) -> Path:
    return local_jur / ".colab_mirror_stamp"


def _drive_manifest_mtime(drive_jur: Path) -> Optional[float]:
    manifest = drive_jur / "_manifest.json"
    if not manifest.is_file():
        return None
    try:
        return manifest.stat().st_mtime
    except OSError:
        return None


def jurisdiction_mirror_up_to_date(drive_jur: Path, local_jur: Path) -> bool:
    """True when local copy exists and matches Drive ``_manifest.json`` mtime stamp."""
    stamp = _mirror_stamp_path(local_jur)
    if not local_jur.is_dir() or not stamp.is_file():
        return False
    drive_m = _drive_manifest_mtime(drive_jur)
    if drive_m is None:
        # No manifest — require at least one pdf/audio locally if drive has media.
        try:
            drive_has = any(
                p.suffix.lower() in {".pdf", ".opus", ".mp3", ".m4a", ".wav", ".mp4"}
                for p in drive_jur.rglob("*")
                if p.is_file() and not p.name.startswith(".")
            )
            local_has = any(
                p.suffix.lower() in {".pdf", ".opus", ".mp3", ".m4a", ".wav", ".mp4"}
                for p in local_jur.rglob("*")
                if p.is_file() and not p.name.startswith(".")
            )
            return local_has if drive_has else local_jur.is_dir()
        except OSError:
            return False
    try:
        stamped = float(stamp.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return abs(stamped - drive_m) < 0.5


def _copy_tree(drive_jur: Path, local_jur: Path) -> None:
    local_jur.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("rsync"):
        subprocess.run(
            [
                "rsync",
                "-a",
                "--delete",
                f"{drive_jur.resolve().as_posix()}/",
                f"{local_jur.resolve().as_posix()}/",
            ],
            check=True,
        )
    else:
        if local_jur.is_dir():
            shutil.rmtree(local_jur)
        shutil.copytree(drive_jur, local_jur)


def mirror_jurisdiction(drive_jur: Path, local_jur: Path, *, force: bool = False) -> bool:
    """
    Copy ``drive_jur`` → ``local_jur`` when missing or stale.

    Returns True if a copy was performed.
    """
    if not force and jurisdiction_mirror_up_to_date(drive_jur, local_jur):
        return False
    with timed_step(f"Local mirror | copy {drive_jur.name} → {local_jur.name}"):
        _copy_tree(drive_jur, local_jur)
    stamp = _mirror_stamp_path(local_jur)
    mtime = _drive_manifest_mtime(drive_jur)
    stamp.write_text(
        str(mtime if mtime is not None else drive_jur.stat().st_mtime),
        encoding="utf-8",
    )
    return True


def remap_inventory_paths(
    inv: MeetingInventory, local_jurisdiction_root: Path
) -> MeetingInventory:
    """Point inventory file paths at the local jurisdiction tree."""
    drive_root = inv.jurisdiction.root.resolve()
    local_root = local_jurisdiction_root.resolve()
    jur = parse_jurisdiction_dir(
        local_root,
        inv.jurisdiction.state_code,
        inv.jurisdiction.scope,
    )

    def _localize(path: Path) -> Path:
        return local_root / path.resolve().relative_to(drive_root)

    return MeetingInventory(
        jurisdiction=jur,
        pdfs=[_localize(p) for p in inv.pdfs],
        audio=[_localize(p) for p in inv.audio],
        images=[_localize(p) for p in inv.images],
    )


def mirror_inventories_to_local_raw(
    inventories: List[MeetingInventory],
    drive_raw_root: Path,
    local_raw_root: Optional[Path] = None,
    *,
    force: bool = False,
) -> Tuple[List[MeetingInventory], Path]:
    """
    Ensure each scoped jurisdiction exists under ``local_raw_root``; return remapped inventories.

    ``drive_raw_root`` stays the canonical Drive path; ``RAW_ROOT`` for §6 should be
    ``local_raw_root`` after this call.
    """
    if not local_raw_mirror_enabled():
        return inventories, drive_raw_root.resolve()

    drive_raw_root = drive_raw_root.resolve()
    local_raw_root = (local_raw_root or default_local_raw_root()).resolve()
    local_raw_root.mkdir(parents=True, exist_ok=True)

    if not _is_drive_path(drive_raw_root):
        # Already local or non-Colab path — nothing to mirror.
        return inventories, drive_raw_root

    remapped: List[MeetingInventory] = []
    copied = 0
    skipped = 0
    with timed_step(f"Local mirror | {len(inventories)} jurisdiction(s)"):
        for inv in inventories:
            drive_jur = inv.jurisdiction.root.resolve()
            rel = _jurisdiction_relpath(drive_jur, drive_raw_root)
            local_jur = local_raw_root / rel
            if mirror_jurisdiction(drive_jur, local_jur, force=force):
                copied += 1
            else:
                skipped += 1
                print(
                    f"  Local mirror | reuse {rel.as_posix()} (already on disk)",
                    flush=True,
                )
            remapped.append(remap_inventory_paths(inv, local_jur))

    print(
        f"Local raw inputs: {local_raw_root} "
        f"({copied} copied, {skipped} reused from /content)",
        flush=True,
    )
    return remapped, local_raw_root
