"""
Log sync — copies run logs to Google Drive.

Supports two backends (tried in order):
  1. Direct filesystem copy to a mounted Google Drive path (preferred on WSL2/Windows)
  2. rclone upload (for Linux servers without Google Drive Desktop)

Logs land at:
  <gdrive_root>/CommunityOne/open-navigator-logs/<machine_id>/<run_type>/<run_id>/

Configuration (env vars — all optional):
  LOG_GDRIVE_MOUNT       Path to mounted Google Drive root
                         (default: /mnt/g/My Drive)
  LOG_GDRIVE_BASE        Sub-path inside the mount
                         (default: CommunityOne/open-navigator-logs)
  LOG_MACHINE_ID         Machine label (default: socket.gethostname())

  RCLONE_GDRIVE_REMOTE   rclone remote name, used only if mount not found
                         (default: gdrive)
"""
import os
import shutil
import socket
import subprocess
from pathlib import Path

from loguru import logger

from scripts.utils.gdrive_paths import gdrive_mount_path


GDRIVE_MOUNT = gdrive_mount_path()
GDRIVE_BASE = os.getenv("LOG_GDRIVE_BASE", "CommunityOne/open-navigator-logs")
MACHINE_ID = os.getenv("LOG_MACHINE_ID", socket.gethostname())
RCLONE_REMOTE = os.getenv("RCLONE_GDRIVE_REMOTE", "gdrive")


def _sync_via_mount(log_dir: Path, run_type: str) -> bool:
    """Copy log_dir into the mounted Google Drive folder."""
    dest = GDRIVE_MOUNT / GDRIVE_BASE / MACHINE_ID / run_type / log_dir.name
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for src_file in log_dir.iterdir():
            # shutil.copy/copy2 fail on NTFS mounts (chmod not permitted); plain write avoids that
            (dest / src_file.name).write_bytes(src_file.read_bytes())
        logger.success(f"Logs copied → {dest}")
        return True
    except Exception as e:
        logger.warning(f"Drive mount copy failed: {e}")
        return False


def _rclone_configured() -> bool:
    try:
        result = subprocess.run(
            ["rclone", "listremotes"], capture_output=True, text=True, timeout=10
        )
        return f"{RCLONE_REMOTE}:" in result.stdout
    except Exception:
        return False


def _sync_via_rclone(log_dir: Path, run_type: str) -> bool:
    """Upload log_dir to Google Drive via rclone."""
    if not _rclone_configured():
        logger.warning(
            f"rclone remote '{RCLONE_REMOTE}' not configured. "
            "Run: rclone config  (add a remote named 'gdrive')"
        )
        return False
    remote_path = f"{RCLONE_REMOTE}:{GDRIVE_BASE}/{MACHINE_ID}/{run_type}/{log_dir.name}"
    try:
        result = subprocess.run(
            ["rclone", "copy", str(log_dir), remote_path, "--stats-one-line"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            logger.success(f"Logs uploaded → {remote_path}")
            return True
        logger.warning(f"rclone exited {result.returncode}: {result.stderr.strip()}")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("rclone sync timed out after 120 s")
        return False
    except Exception as e:
        logger.warning(f"rclone sync failed: {e}")
        return False


def sync_logs(log_dir: Path, run_type: str, project_root: Path | None = None) -> bool:
    """
    Upload a run's log directory to Google Drive.

    Tries the mounted Drive path first; falls back to rclone.
    Always non-fatal — failures are logged as warnings.
    """
    if not log_dir.exists():
        logger.warning(f"Log dir {log_dir} does not exist — nothing to sync")
        return False

    try:
        display = log_dir.relative_to(project_root) if project_root else log_dir
    except ValueError:
        display = log_dir.resolve().relative_to(project_root.resolve()) if project_root else log_dir
    logger.info(f"Syncing {display}  [machine: {MACHINE_ID}]")

    if GDRIVE_MOUNT.exists():
        return _sync_via_mount(log_dir, run_type)

    logger.debug(f"Drive mount {GDRIVE_MOUNT} not found — trying rclone")
    return _sync_via_rclone(log_dir, run_type)
