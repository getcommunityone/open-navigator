"""Colab GPU runs: secrets, GPU facts, compute units and the landing-volume / Drive storage they read and write.

Shared by the Colab runners (``llm.gpu.colab_policy_analyze``, #511). The pattern is PR #489's
(``llm.gpu.colab_diarize``, still open when this was written): the Databricks Files API with ``DATABRICKS_HOST`` /
``DATABRICKS_TOKEN`` from Colab secrets or the environment, else a mounted Google Drive folder. Paths are relative to
the landing volume ``/Volumes/open_navigator/open_navigator_landing/crawl``, and the Drive folder mirrors it, so a run
reads and writes the same relative paths either way. Tokens are never printed or logged.

Colab has no API for compute units (CU). A row's CU is GPU seconds times a per-GPU rate and says it is an estimate; a
batch's measured CU is the balance the owner reads in Colab's Resources panel before minus after.
"""

from __future__ import annotations

import io
import os
import posixpath
import re
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

LANDING_VOLUME = "/Volumes/open_navigator/open_navigator_landing/crawl"
DRIVE_ROOT = "/content/drive/MyDrive/open-navigator/crawl"   # fallback with no Databricks credentials

# Colab compute units per GPU-hour, as reported by Colab users in 2024-2025 (Colab publishes no table). Approximate:
# Colab's Resources panel shows the live rate for the attached GPU; pass it with --cu-per-hour to use it instead.
COLAB_CU_PER_HOUR = {"T4": 1.76, "L4": 4.82, "A100": 11.77}
# Colab's pay-as-you-go price, US$9.99 for 100 compute units (colab.research.google.com/signup).
COLAB_USD_PER_CU = 9.99 / 100

_RUN_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ------------------------------------------------------------------------------------------------- plain helpers
def get_secret(name: str, userdata: Any = None) -> str | None:
    """A secret from Colab's secrets (``google.colab.userdata``), else the environment; None when neither has it."""
    if userdata is None:
        try:
            from google.colab import userdata as colab_userdata  # type: ignore[import-not-found]

            userdata = colab_userdata
        except ImportError:
            userdata = None
    if userdata is not None:
        try:
            value = userdata.get(name)
        except Exception:  # noqa: BLE001 - SecretNotFoundError / NotebookAccessError: fall back to the environment
            value = None
        if value and str(value).strip():
            return str(value).strip()
    value = (os.environ.get(name) or "").strip()
    return value or None


def redact(text: str, secrets: Iterable[str | None]) -> str:
    """``text`` with every secret value replaced by ``***``."""
    for value in secrets:
        if value and len(value) >= 4:
            text = text.replace(value, "***")
    return text


def gpu_kind(name: str | None) -> str:
    """The short GPU type ("T4", "L4", "A100", ...) from an ``nvidia-smi`` name such as "NVIDIA A100-SXM4-40GB"."""
    if not name:
        return "NONE"
    for kind in ("A100", "H100", "L4", "T4", "V100", "P100", "A10G", "L40S"):
        if re.search(rf"\b{kind}\b", name.upper().replace("-", " ")):
            return kind
    return name.strip().upper()


def gpu_memory_gb() -> float | None:
    """Total memory of the first GPU in GB, from ``nvidia-smi``; None with no GPU."""
    import subprocess

    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    first = (out.stdout or "").strip().splitlines()[:1]
    try:
        return round(float(first[0]) / 1024.0, 1) if first else None
    except ValueError:
        return None


def check_run_date(run_date: str) -> str:
    if not _RUN_DATE.match(run_date or ""):
        raise ValueError(f"run date must be YYYY-MM-DD, got {run_date!r}")
    datetime.strptime(run_date, "%Y-%m-%d")
    return run_date


def today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def latest_child(store: "Store", rel_dir: str) -> str | None:
    """The newest dated folder name under ``rel_dir`` (names start ``YYYY-MM-DD``, so the last in sort order), or None."""
    names = sorted(n for n in store.list_names(rel_dir) if _RUN_DATE.match(n[:10]))
    return names[-1] if names else None


def clean_rel(path: str, volume: str = LANDING_VOLUME) -> str:
    """A path relative to the volume: ``crawl/x``, ``x`` and ``/Volumes/.../crawl/x`` all give ``x``.
    Raises for a path that leaves it."""
    p = (path or "").strip()
    root = volume.rstrip("/")
    if p.startswith(root + "/"):
        p = p[len(root) + 1:]
    elif p.startswith(DRIVE_ROOT + "/"):
        p = p[len(DRIVE_ROOT) + 1:]
    elif p.startswith("/"):
        raise ValueError(f"{path!r} is not inside the landing volume {root} or the Drive folder {DRIVE_ROOT}")
    if p.startswith("crawl/"):
        p = p[len("crawl/"):]
    norm = posixpath.normpath(p)
    if norm in (".", "") or norm == ".." or norm.startswith("../"):
        raise ValueError(f"{path!r} points outside the landing volume {root}")
    return norm


def estimated_compute_units(seconds: float, gpu: str, cu_per_hour: float | None = None) -> float | None:
    """GPU seconds times the CU rate (the one given, else the documented one for the GPU); None with no rate."""
    rate = cu_per_hour if cu_per_hour is not None else COLAB_CU_PER_HOUR.get(gpu.upper())
    return None if rate is None else round(float(seconds) / 3600.0 * float(rate), 4)


def measured_batch_cu(balance_before: float | None, balance_after: float | None) -> float | None:
    """CU a batch used, from the balance read before and after; None if either is missing or the balance went up."""
    if balance_before is None or balance_after is None:
        return None
    used = float(balance_before) - float(balance_after)
    return round(used, 4) if used >= 0 else None


def apportion(total: float, weights: dict[str, float]) -> dict[str, float]:
    """``total`` split over the keys in proportion to their weights (GPU seconds); empty when nothing ran."""
    positive = {k: float(w) for k, w in weights.items() if w and float(w) > 0}
    whole = sum(positive.values())
    if not positive or whole <= 0:
        return {}
    return {k: round(total * w / whole, 4) for k, w in positive.items()}


# ---------------------------------------------------------------------------------------------------- storage
class Store(Protocol):
    """Where inputs are read from and results are written to, by path relative to the landing volume."""

    label: str

    def list_names(self, rel_dir: str) -> set[str]: ...
    def read_text(self, rel: str) -> str | None: ...
    def write_bytes(self, rel: str, data: bytes) -> None: ...


class LocalStore:
    """A folder standing in for the volume: a mounted Google Drive, a laptop folder, or a temp folder in tests."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.label = f"folder {self.root}"

    def _path(self, rel: str) -> Path:
        return self.root / rel

    def list_names(self, rel_dir: str) -> set[str]:
        d = self._path(rel_dir)
        return {p.name for p in d.iterdir()} if d.is_dir() else set()

    def read_text(self, rel: str) -> str | None:
        p = self._path(rel)
        return p.read_text(encoding="utf-8") if p.is_file() else None

    def write_bytes(self, rel: str, data: bytes) -> None:
        p = self._path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".partial")
        tmp.write_bytes(data)
        tmp.replace(p)   # a disconnect mid-write never leaves a half file that resume would take as done


class DatabricksVolumeStore:
    """The landing volume through the Databricks Files API (``databricks-sdk`` ``WorkspaceClient.files``)."""

    def __init__(self, client: Any, volume: str = LANDING_VOLUME):
        self.client = client
        self.volume = volume.rstrip("/")
        self.label = f"volume {self.volume}"

    def _path(self, rel: str) -> str:
        return f"{self.volume}/{rel}"

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        return type(exc).__name__ in ("NotFound", "ResourceDoesNotExist") or "404" in str(exc)

    def list_names(self, rel_dir: str) -> set[str]:
        try:
            entries = self.client.files.list_directory_contents(self._path(rel_dir))
            return {posixpath.basename((e.path or "").rstrip("/")) or e.name for e in entries}
        except Exception as exc:  # noqa: BLE001
            if self._is_not_found(exc):
                return set()
            raise

    def read_text(self, rel: str) -> str | None:
        try:
            resp = self.client.files.download(self._path(rel))
        except Exception as exc:  # noqa: BLE001
            if self._is_not_found(exc):
                return None
            raise
        return resp.contents.read().decode("utf-8")

    def write_bytes(self, rel: str, data: bytes) -> None:
        self.client.files.upload(self._path(rel), io.BytesIO(data), overwrite=True)


def make_store(volume: str = LANDING_VOLUME, drive_root: str | None = DRIVE_ROOT, userdata: Any = None) -> Store:
    """The Databricks volume when DATABRICKS_HOST and DATABRICKS_TOKEN are set (Colab secrets or environment), else
    the Drive folder. Raises when neither is available."""
    host, token = get_secret("DATABRICKS_HOST", userdata), get_secret("DATABRICKS_TOKEN", userdata)
    if host and token:
        from databricks.sdk import WorkspaceClient

        return DatabricksVolumeStore(WorkspaceClient(host=host, token=token, auth_type="pat"), volume)
    if drive_root and Path(drive_root).is_dir():
        logger.warning("No DATABRICKS_HOST / DATABRICKS_TOKEN; reading and writing the folder {}", drive_root)
        return LocalStore(drive_root)
    raise RuntimeError("No DATABRICKS_HOST / DATABRICKS_TOKEN secrets and no Drive folder at "
                       f"{drive_root}; add the secrets or mount Drive (see colab-gemma-policy-analysis.md)")
