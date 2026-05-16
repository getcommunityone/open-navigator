#!/usr/bin/env python3
"""
Copy scraped-meetings **inventory** folders from the local cache to Google Drive (or ``--local`` staging).

**Default (no flags):** syncs **only** these four subtrees under ``<src-root>/`` (Tuscaloosa + Big Timber)::

  AL/county/county_01125
  MT/county/county_30097
  AL/municipality/municipality_0177256
  MT/municipality/municipality_3006475

Use ``--all-cache`` to copy the **entire** ``scraped_meetings`` tree instead.

Run from repo root::

  python scripts/colab/01_copy_scraped_meetings_cache_to_gdrive.py --dry-run
  python scripts/colab/01_copy_scraped_meetings_cache_to_gdrive.py

**Destination** defaults to ``<My Drive>/CommunityOne/hackathons/2026_Gemma_4_Good/01_raw_inputs`` via
``scraped_meetings_gdrive_mirror_root()`` in ``scripts/utils/gdrive_paths.py`` (env:
``LOG_GDRIVE_MOUNT``, ``SCRAPED_MEETINGS_GDRIVE_MIRROR``).

Configuration (env, optional):

  LOG_GDRIVE_MOUNT               Mounted Drive root (default ``/mnt/g/My Drive``)
  SCRAPED_MEETINGS_GDRIVE_MIRROR Absolute override for the mirror *root*
  SCRAPED_MEETINGS_ROOT          Local cache root override
  RCLONE_GDRIVE_REMOTE           rclone remote name (default ``gdrive``)

If **rclone** is configured (``rclone listremotes`` shows ``gdrive:``), uploads via rclone when
the Drive folder is not visible in WSL (same idea as ``log_sync``). This script does not mount Drive.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.utils.gdrive_paths import (  # noqa: E402
    SCRAPED_MEETINGS_GDRIVE_REL,
    resolve_scraped_meetings_output_root,
    resolved_gdrive_mount_path,
    scraped_meetings_gdrive_mirror_root,
    scraped_meetings_gdrive_rclone_remote_subpath,
)

# Tuscaloosa County AL, Big Timber area MT, Tuscaloosa city, Big Timber city (default sync set)
DEFAULT_REL_PATHS = (
    "AL/county/county_01125",
    "MT/county/county_30097",
    "AL/municipality/municipality_0177256",
    "MT/municipality/municipality_3006475",
)

RCLONE_REMOTE = os.getenv("RCLONE_GDRIVE_REMOTE", "gdrive")


def _rclone_configured() -> bool:
    try:
        result = subprocess.run(
            ["rclone", "listremotes"], capture_output=True, text=True, timeout=10
        )
        return f"{RCLONE_REMOTE}:" in result.stdout
    except Exception:
        return False


def _resolve_mkdir_anchor(dest_root: Path) -> Path | None:
    try:
        anchor = resolved_gdrive_mount_path().resolve()
        dest_root = dest_root.resolve()
    except OSError:
        return None
    if not anchor.is_dir():
        return None
    try:
        dest_root.relative_to(anchor)
    except ValueError:
        return None
    return anchor


def _mkdir_descendants_only(target: Path, anchor: Path) -> None:
    target = target.resolve()
    anchor = anchor.resolve()
    rel = target.relative_to(anchor)
    cur = anchor
    for part in rel.parts:
        cur = cur / part
        if not cur.exists():
            cur.mkdir(exist_ok=False)


def _mkdir_parent_for_output(out: Path, *, mkdir_anchor: Path | None) -> None:
    parent = out.parent
    if mkdir_anchor is not None:
        try:
            parent.resolve().relative_to(mkdir_anchor.resolve())
        except ValueError:
            parent.mkdir(parents=True, exist_ok=True)
            return
        _mkdir_descendants_only(parent, mkdir_anchor)
    else:
        parent.mkdir(parents=True, exist_ok=True)


def _copy_tree_rclone(src: Path, rel: str) -> tuple[int, int]:
    base = scraped_meetings_gdrive_rclone_remote_subpath()
    remote_dir = f"{RCLONE_REMOTE}:{base}/{rel}" if rel else f"{RCLONE_REMOTE}:{base}"
    try:
        result = subprocess.run(
            [
                "rclone",
                "copy",
                str(src),
                remote_dir,
                "--stats-one-line",
                "--non-interactive",
            ],
            capture_output=True,
            text=True,
            timeout=86400,
        )
    except FileNotFoundError:
        print(
            "rclone not found on PATH. Install rclone or use direct copy without --rclone.",
            file=sys.stderr,
        )
        return 0, 0
    except subprocess.TimeoutExpired:
        print("rclone timed out.", file=sys.stderr)
        return 0, 0
    if result.returncode != 0:
        print(f"rclone failed ({result.returncode}): {result.stderr.strip()}", file=sys.stderr)
        return 0, 0
    n_files = sum(1 for _ in src.rglob("*") if _.is_file())
    n_bytes = sum(p.stat().st_size for p in src.rglob("*") if p.is_file())
    return n_files, n_bytes


def _copy_tree_files(
    src: Path,
    dst: Path,
    *,
    dry_run: bool,
    mkdir_anchor: Path | None,
) -> tuple[int, int]:
    n_files = 0
    n_bytes = 0
    if not src.is_dir():
        return 0, 0
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        out = dst / rel
        n_bytes += path.stat().st_size
        n_files += 1
        if dry_run:
            continue
        try:
            _mkdir_parent_for_output(out, mkdir_anchor=mkdir_anchor)
            out.write_bytes(path.read_bytes())
        except PermissionError as exc:
            hint = (
                (mkdir_anchor / SCRAPED_MEETINGS_GDRIVE_REL)
                if mkdir_anchor
                else out.parent
            )
            print(
                f"\nPermission denied while writing {out} ({exc}).\n"
                "Google Drive's WSL mount often blocks creating folders from WSL.\n"
                f"Fix: in Windows Explorer ensure this folder exists (create parents if needed):\n"
                f"  {hint}\n"
                "Then re-run; or upload via rclone:\n"
                "  python scripts/colab/01_copy_scraped_meetings_cache_to_gdrive.py --rclone\n",
                file=sys.stderr,
            )
            raise SystemExit(3) from exc
    return n_files, n_bytes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy fixed scraped_meetings inventory folders to Google Drive (use --all-cache for full tree)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned copies without writing",
    )
    parser.add_argument(
        "--src-root",
        type=Path,
        default=None,
        help="Local scraped_meetings root (default: resolve_scraped_meetings_output_root())",
    )
    parser.add_argument(
        "--dest-root",
        type=Path,
        default=None,
        help="Mirror root (default: scraped_meetings_gdrive_mirror_root())",
    )
    parser.add_argument(
        "--rclone",
        action="store_true",
        help="Force rclone upload. "
        f"Remote from RCLONE_GDRIVE_REMOTE (default {RCLONE_REMOTE!r}).",
    )
    parser.add_argument(
        "--all-cache",
        action="store_true",
        help="Copy the entire scraped_meetings tree under src-root (default: only the four inventory paths).",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Write to <repo>/data/export/scraped_meetings_mirror (no Drive mount).",
    )
    args = parser.parse_args()

    if args.local and args.dest_root:
        parser.error("--local already sets dest; do not pass --dest-root")
    if args.local and args.rclone:
        parser.error("--local and --rclone cannot be used together")

    src_root = (
        args.src_root.expanduser().resolve()
        if args.src_root
        else resolve_scraped_meetings_output_root()
    )
    if args.local:
        dest_root = (_repo_root / "data" / "export" / "scraped_meetings_mirror").resolve()
    elif args.dest_root:
        dest_root = args.dest_root.expanduser().resolve()
    else:
        dest_root = scraped_meetings_gdrive_mirror_root()

    print(f"Source root: {src_root}")
    print(f"Dest root:   {dest_root}")
    if args.local:
        print(
            "(mode: --local — no Google Drive mount; output is under the repo in gitignored data/. "
            "Upload this folder to Drive when you have one.)\n"
        )

    mkdir_anchor: Path | None = None
    effective_rclone = args.rclone
    if not args.dry_run and not args.local:
        if not effective_rclone:
            mkdir_anchor = _resolve_mkdir_anchor(dest_root)
            gd = resolved_gdrive_mount_path()
            if mkdir_anchor is None and dest_root.resolve() == scraped_meetings_gdrive_mirror_root().resolve():
                if not gd.is_dir():
                    if _rclone_configured():
                        print(
                            f"\nNote: No Google Drive folder at {gd} in WSL — uploading via "
                            f"rclone ({RCLONE_REMOTE}:) instead (same fallback as log_sync).\n",
                        )
                        effective_rclone = True
                        mkdir_anchor = None
                    else:
                        print(
                            f"\nERROR: Google Drive is not available at {gd}.\n"
                            "This script cannot mount Google Drive from WSL — enable Google Drive for Desktop in Windows, "
                            "configure rclone (rclone config → remote named gdrive by default), or pick one of:\n"
                            "  --local     copy to  data/export/scraped_meetings_mirror  in the repo (then upload via Explorer)\n"
                            "  --dest-root PATH   copy to any writable folder you choose\n"
                            "  export LOG_GDRIVE_MOUNT='.../My Drive'   if Drive is under a different WSL path\n"
                            "  --rclone    force upload with rclone\n",
                            file=sys.stderr,
                        )
                        return 2

    if effective_rclone and not args.dry_run:
        print(f"Mode:        rclone → {RCLONE_REMOTE}:{scraped_meetings_gdrive_rclone_remote_subpath()}/…")
    if args.dry_run:
        print("(dry-run — no writes)")

    total_files = 0
    total_bytes = 0
    missing: list[str] = []

    full_copy = args.all_cache

    if full_copy:
        if not src_root.is_dir():
            print(f"Source missing or not a directory: {src_root}", file=sys.stderr)
            return 2
        if effective_rclone:
            if args.dry_run:
                fc = sum(1 for _ in src_root.rglob("*") if _.is_file())
                bc = sum(p.stat().st_size for p in src_root.rglob("*") if p.is_file())
                print(f"  would rclone: {fc} files, {bc / 1e6:.2f} MB  (full tree under {src_root.name}/)")
                total_files, total_bytes = fc, bc
            else:
                fc, bc = _copy_tree_rclone(src_root, "")
                label = "rclone OK" if fc else "rclone FAILED"
                print(f"  {label}: {fc} files, {bc / 1e6:.2f} MB  (full tree)")
                total_files, total_bytes = fc, bc
        else:
            fc, bc = _copy_tree_files(
                src_root, dest_root, dry_run=args.dry_run, mkdir_anchor=mkdir_anchor
            )
            action = "would copy" if args.dry_run else "copied"
            print(f"  {action}: {fc} files, {bc / 1e6:.2f} MB  (full tree)")
            total_files, total_bytes = fc, bc

        if not args.dry_run and total_files == 0:
            print("Nothing to copy (empty tree?).", file=sys.stderr)
            return 1
        if not args.dry_run and total_files > 0:
            print(f"\nDone. {total_files} files, {total_bytes / 1e6:.2f} MB total.")
        if args.dry_run and total_files == 0:
            print("Nothing would be copied (empty tree?).", file=sys.stderr)
            return 1
        return 0

    for rel in DEFAULT_REL_PATHS:
        src = src_root / rel
        dst = dest_root / rel
        if not src.is_dir():
            missing.append(str(src))
            print(f"  SKIP (missing): {src}")
            continue
        if effective_rclone:
            if args.dry_run:
                fc = sum(1 for _ in src.rglob("*") if _.is_file())
                bc = sum(p.stat().st_size for p in src.rglob("*") if p.is_file())
                print(f"  would rclone: {fc} files, {bc / 1e6:.2f} MB  {rel}")
            else:
                fc, bc = _copy_tree_rclone(src, rel)
                label = "rclone OK" if fc else "rclone FAILED"
                print(f"  {label}: {fc} files, {bc / 1e6:.2f} MB  {rel}")
        else:
            fc, bc = _copy_tree_files(
                src, dst, dry_run=args.dry_run, mkdir_anchor=mkdir_anchor
            )
            action = "would copy" if args.dry_run else "copied"
            print(f"  {action}: {fc} files, {bc / 1e6:.2f} MB  {rel}")
        total_files += fc
        total_bytes += bc

    if missing:
        print(f"\nWarning: {len(missing)} source path(s) missing — skipped.", file=sys.stderr)

    if not args.dry_run and total_files == 0 and not missing:
        print("Nothing to copy (empty trees?).", file=sys.stderr)
        return 1

    if not args.dry_run and total_files > 0:
        print(f"\nDone. {total_files} files, {total_bytes / 1e6:.2f} MB total.")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
