"""Speech-to-text and speaker separation (WhisperX) on the owner's Colab GPU, against the landing volume (#297).

Colab is where GPU runs go (``web_docs/docs/development/gpu-compute-decisions.md``, #357); the Modal runner
(``llm.gpu.modal_diarize``) is kept but isn't used for runs. The notebook ``notebooks/colab_gpu_diarize.ipynb`` is a
thin shell around this module, and the steps are in ``web_docs/docs/deployment/colab-gpu-diarize.md``.

    python -m llm.gpu.colab_diarize --items crawl/audio/2026-11-03_council.opus --limit 3
    python -m llm.gpu.colab_diarize --items https://example.org/media/516.mp4 --dry-run

- **Input:** landing-volume paths (``crawl/audio/<file>``, ``audio/<file>`` or the full ``/Volumes/...`` path) or
  direct media URLs. YouTube blocks cloud IPs, so YouTube audio is fetched on the laptop and uploaded first.
- **Output:** ``<volume>/diarized/<run_date>/<name>.diarized.json``, i.e. ``.../crawl/diarized/<run_date>/``.
- **Resume:** an item whose output already exists for that run date is skipped, so re-running the same cell after a
  Colab disconnect carries on where it stopped.
- **Usage:** one row per item appended to ``diarized/<run_date>/usage.jsonl`` in the Modal row's shape, plus the GPU,
  measured seconds, status and Colab compute units (CU). Colab has no API for CU, so a row's CU is GPU seconds times a
  per-GPU rate and says it is an estimate; the batch's measured CU comes from the balance the owner reads in Colab's
  Resources panel before and after (``record_measured_cu``). The ``llm.usage`` ``gpu_run`` rows are copied next to it.
- **Volume I/O:** the Databricks Files API (``databricks-sdk``) with ``DATABRICKS_HOST`` / ``DATABRICKS_TOKEN`` from
  Colab secrets or the environment; without them, a mounted Google Drive folder. Tokens are never printed or logged.

A paid GPU run starts only on the owner's explicit yes for that run (``AGENTS.md``, "GPU and paid compute").
"""

from __future__ import annotations

import argparse
import io
import json
import posixpath
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from llm.gpu.diarize_common import (
    DEFAULT_LIMIT,
    DEFAULT_MODEL_SIZE,
    MEETING_LANGUAGE,
    STEP_NAME,
    base_usage_row,
    exit_code,
    fetch_media,
    is_url,
    output_name,
    plan_batch,
)

PLATFORM = "colab"
LANDING_VOLUME = "/Volumes/open_navigator/open_navigator_landing/crawl"
VOLUME_NAME_PREFIX = "crawl/"                 # items may name the volume itself: crawl/audio/<file>
DIARIZED_DIR = "diarized"
USAGE_FILE = "usage.jsonl"
DRIVE_ROOT = "/content/drive/MyDrive/open-navigator/crawl"   # fallback with no Databricks credentials
SECRET_NAMES = ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "HF_TOKEN")
TOKEN_NAMES = ("DATABRICKS_TOKEN", "HF_TOKEN")

# Colab compute units per GPU-hour, as reported by Colab users in 2024-2025 (Colab publishes no table). Approximate:
# Colab's Resources panel shows the live rate for the attached GPU; pass it with --cu-per-hour to use it instead.
COLAB_CU_PER_HOUR = {"T4": 1.76, "L4": 4.82, "A100": 11.77}
# Colab's pay-as-you-go price, US$9.99 for 100 compute units (colab.research.google.com/signup).
COLAB_USD_PER_CU = 9.99 / 100

_RUN_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ------------------------------------------------------------------------------------------------- plain helpers
def get_secret(name: str, userdata: Any = None) -> str | None:
    """A secret from Colab's secrets (``google.colab.userdata``), else the environment; None when neither has it."""
    import os

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
    """The short GPU type ("T4", "L4", "A100", ...) from an ``nvidia-smi`` name such as "Tesla T4"."""
    if not name:
        return "NONE"
    for kind in ("A100", "H100", "L4", "T4", "V100", "P100", "A10G", "L40S"):
        if re.search(rf"\b{kind}\b", name.upper()):
            return kind
    return name.strip().upper()


def check_run_date(run_date: str) -> str:
    if not _RUN_DATE.match(run_date or ""):
        raise ValueError(f"run date must be YYYY-MM-DD, got {run_date!r}")
    datetime.strptime(run_date, "%Y-%m-%d")
    return run_date


def today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def volume_rel(item: str, volume: str = LANDING_VOLUME) -> str:
    """An item's path inside the landing volume: ``crawl/audio/a.opus``, ``audio/a.opus`` and
    ``/Volumes/.../crawl/audio/a.opus`` all give ``audio/a.opus``. Raises for a path that leaves the volume."""
    path = item.strip()
    root = volume.rstrip("/")
    if path.startswith(root + "/"):
        path = path[len(root) + 1:]
    elif path.startswith("/"):
        raise ValueError(f"{item!r} is not inside the landing volume {root}")
    if path.startswith(VOLUME_NAME_PREFIX):
        path = path[len(VOLUME_NAME_PREFIX):]
    norm = posixpath.normpath(path)
    if norm in (".", "") or norm.startswith("../") or norm == "..":
        raise ValueError(f"{item!r} points outside the landing volume {root}")
    return norm


def item_output_name(item: str, volume: str = LANDING_VOLUME) -> str:
    """``<name>.diarized.json`` for a URL or a volume path (the volume's own ``crawl/`` prefix doesn't count)."""
    return output_name(item if is_url(item) else volume_rel(item, volume))


def output_dir_rel(run_date: str) -> str:
    return f"{DIARIZED_DIR}/{check_run_date(run_date)}"


def output_rel(item: str, run_date: str, volume: str = LANDING_VOLUME) -> str:
    """Where an item's result goes, relative to the volume: ``diarized/<run_date>/<name>.diarized.json``."""
    return f"{output_dir_rel(run_date)}/{item_output_name(item, volume)}"


def split_done(batch: list[str], existing_names: Iterable[str], volume: str = LANDING_VOLUME) -> tuple[list[str], list[str]]:
    """(to run, already done) for a batch, given the file names already in the run date's output folder."""
    existing = set(existing_names)
    todo: list[str] = []
    done: list[str] = []
    for item in batch:
        (done if item_output_name(item, volume) in existing else todo).append(item)
    return todo, done


def estimated_compute_units(seconds: float, gpu: str, cu_per_hour: float | None = None) -> float | None:
    """GPU seconds times the CU rate (the one given, else the documented one for the GPU); None with no rate."""
    rate = cu_per_hour if cu_per_hour is not None else COLAB_CU_PER_HOUR.get(gpu.upper())
    return None if rate is None else round(float(seconds) / 3600.0 * float(rate), 4)


def measured_batch_cu(balance_before: float | None, balance_after: float | None) -> float | None:
    """CU a batch used, from the balance read in Colab's Resources panel before and after; None if either is missing
    or the balance went up (a top-up or a new month in between makes it unreadable)."""
    if balance_before is None or balance_after is None:
        return None
    used = float(balance_before) - float(balance_after)
    return round(used, 4) if used >= 0 else None


def usage_row(item: str, gpu: str, started_ts: str, seconds: float, status_code: str,
              cu_per_hour: float | None = None) -> dict:
    """One usage row per item: the Modal row's fields plus Colab compute units, labelled as an estimate."""
    gpu = gpu.upper()
    cu = estimated_compute_units(seconds, gpu, cu_per_hour)
    rate = cu_per_hour if cu_per_hour is not None else COLAB_CU_PER_HOUR.get(gpu)
    origin = "rate entered from Colab's Resources panel" if cu_per_hour is not None else f"documented {gpu} rate"
    row = base_usage_row(PLATFORM, item, gpu, started_ts, seconds, status_code,
                         None if cu is None else round(cu * COLAB_USD_PER_CU, 6))
    row.update({
        "compute_units": cu,
        "compute_units_source": (f"estimate: GPU seconds x {rate} CU/hour ({origin})" if cu is not None
                                 else "unknown: no CU rate for this GPU; read Colab's Resources panel"),
        "cu_per_hour": rate,
    })
    return row


def summarize(result: dict | None) -> dict:
    """Segments, distinct speakers and speaking time of a ``diarize_audio_whisperx`` result (no transcript text)."""
    segments = (result or {}).get("segments") or []
    speakers = {s.get("speaker") for s in segments if s.get("speaker")}
    speaking = sum(max(0.0, float(s.get("end") or 0) - float(s.get("start") or 0)) for s in segments)
    return {"segments": len(segments), "speakers": len(speakers), "speaking_minutes": round(speaking / 60.0, 1)}


def summary_table(rows: list[dict]) -> str:
    """A plain-text table of a batch: item, status, segments, speakers, speaking time, GPU seconds, CU."""
    head = ("item", "status", "segments", "speakers", "speaking_min", "gpu_seconds", "cu (estimate)")
    lines = [head]
    for r in rows:
        lines.append((
            str(r.get("item_name", ""))[-60:],
            str(r.get("run_status_code", "")),
            "" if r.get("segments") is None else str(r["segments"]),
            "" if r.get("speakers") is None else str(r["speakers"]),
            "" if r.get("speaking_minutes") is None else f"{r['speaking_minutes']:.1f}",
            "" if r.get("duration_seconds") is None else f"{r['duration_seconds']:.0f}",
            "" if r.get("compute_units") is None else f"{r['compute_units']:.3f}",
        ))
    widths = [max(len(line[i]) for line in lines) for i in range(len(head))]
    out = ["  ".join(c.ljust(w) for c, w in zip(line, widths)) for line in lines]
    ran = [r for r in rows if r.get("duration_seconds") is not None and r.get("run_status_code") != "skipped"]
    cus = [r["compute_units"] for r in ran if r.get("compute_units") is not None]
    out.append(f"{sum(r.get('run_status_code') == 'ok' for r in ran)}/{len(ran)} ran ok; "
               f"{sum(r['duration_seconds'] for r in ran):.0f} GPU seconds; ~{sum(cus):.3f} CU (estimate)")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------------- storage
class Store(Protocol):
    """Where audio is read from and results are written to, by path relative to the landing volume."""

    label: str

    def list_names(self, rel_dir: str) -> set[str]: ...
    def local_copy(self, rel: str, dest_dir: Path) -> Path: ...
    def read_text(self, rel: str) -> str | None: ...
    def write_bytes(self, rel: str, data: bytes) -> None: ...


class LocalStore:
    """A folder standing in for the volume: a mounted Google Drive, or a temp folder in tests."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.label = f"folder {self.root}"

    def _path(self, rel: str) -> Path:
        return self.root / rel

    def list_names(self, rel_dir: str) -> set[str]:
        d = self._path(rel_dir)
        return {p.name for p in d.iterdir()} if d.is_dir() else set()

    def local_copy(self, rel: str, dest_dir: Path) -> Path:
        p = self._path(rel)
        if not p.is_file():
            raise FileNotFoundError(f"{rel} not found in {self.label}")
        return p

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

    def local_copy(self, rel: str, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / posixpath.basename(rel)
        resp = self.client.files.download(self._path(rel))
        with dest.open("wb") as f:
            shutil.copyfileobj(resp.contents, f, 1 << 20)
        return dest

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
        logger.warning("No DATABRICKS_HOST / DATABRICKS_TOKEN; reading and writing the Drive folder {}", drive_root)
        return LocalStore(drive_root)
    raise RuntimeError("No DATABRICKS_HOST / DATABRICKS_TOKEN secrets and no Drive folder at "
                       f"{drive_root}; add the secrets or mount Drive (see colab-gpu-diarize.md)")


def append_usage(store: Store, run_date: str, rows: list[dict]) -> None:
    """Append rows to ``diarized/<run_date>/usage.jsonl`` (read, add, write: the Files API has no append)."""
    rel = f"{output_dir_rel(run_date)}/{USAGE_FILE}"
    text = store.read_text(rel) or ""
    if text and not text.endswith("\n"):
        text += "\n"
    text += "".join(json.dumps(r) + "\n" for r in rows)
    store.write_bytes(rel, text.encode("utf-8"))


def record_measured_cu(store: Store, run_date: str, balance_before: float | None, balance_after: float | None,
                       gpu: str) -> dict | None:
    """Append the batch's measured CU (the Resources panel balance before minus after) as one usage row."""
    used = measured_batch_cu(balance_before, balance_after)
    if used is None:
        return None
    row = {
        "platform_name": PLATFORM,
        "step_name": STEP_NAME,
        "row_kind": "batch_measured_cu",
        "gpu_name": gpu.upper(),
        "recorded_ts": datetime.now(UTC).isoformat(),
        "cu_balance_before": float(balance_before),
        "cu_balance_after": float(balance_after),
        "compute_units": used,
        "compute_units_source": "measured: Colab Resources panel balance before minus after",
        "is_estimated": False,
    }
    append_usage(store, run_date, [row])
    return row


def copy_gpu_run_rows(store: Store, run_date: str, session_tag: str) -> None:
    """Copy this session's ``llm.usage`` ``gpu_runs_*.jsonl`` files to ``diarized/<run_date>/llm_usage/``."""
    from llm.usage.calls import usage_log_dir

    for path in sorted(usage_log_dir().glob("gpu_runs_*.jsonl")):
        store.write_bytes(f"{output_dir_rel(run_date)}/llm_usage/{path.stem}_{session_tag}.jsonl", path.read_bytes())


# ------------------------------------------------------------------------------------------------------- run
DiarizeFn = Callable[..., dict]


def _whisperx(audio: Path, *, model_size: str, hf_token: str | None) -> dict:
    from llm.gemini.diarize_postprocess import diarize_audio_whisperx

    return diarize_audio_whisperx(audio, model_size=model_size, device="cuda", hf_token=hf_token,
                                  language=MEETING_LANGUAGE, allow_no_speakers=True)


def run_batch(items: list[str], store: Store, *, run_date: str, limit: int = DEFAULT_LIMIT,
              model_size: str = DEFAULT_MODEL_SIZE, gpu: str = "T4", cu_per_hour: float | None = None,
              hf_token: str | None = None, secrets: Iterable[str | None] = (), volume: str = LANDING_VOLUME,
              workdir: Path | None = None, diarize_fn: DiarizeFn | None = None, dry_run: bool = False) -> list[dict]:
    """Run a batch; returns one row per item (usage fields plus segments, speakers and speaking time).

    Items whose output exists for ``run_date`` are skipped. Each finished item's result and usage row are written
    before the next starts, so a disconnect loses at most the item in progress. Transcript text is never logged.
    """
    from llm.usage.gpu import gpu_run

    check_run_date(run_date)
    secrets = [s for s in secrets if s]
    batch = plan_batch(items, limit)
    todo, done = split_done(batch, store.list_names(output_dir_rel(run_date)), volume)
    rows: list[dict] = [{"item_name": i, "run_status_code": "skipped", "output_rel": output_rel(i, run_date, volume)}
                        for i in done]
    for item in done:
        logger.info("skip {}: output already in {} for {}", item, store.label, run_date)
    if dry_run:
        for item in todo:
            logger.info("would run {} -> {}", item, output_rel(item, run_date, volume))
            rows.append({"item_name": item, "run_status_code": "planned", "output_rel": output_rel(item, run_date, volume)})
        return rows
    diarize = diarize_fn or _whisperx
    base = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="colab_diarize_"))
    for item in todo:
        started = datetime.now(UTC).isoformat()
        t0 = time.monotonic()
        tmp = base / re.sub(r"[^A-Za-z0-9]+", "_", item)[-80:]
        out_rel = output_rel(item, run_date, volume)
        try:
            with gpu_run(STEP_NAME, device="cuda", item_name=item):
                audio = fetch_media(item, tmp) if is_url(item) else store.local_copy(volume_rel(item, volume), tmp)
                result = diarize(audio, model_size=model_size, hf_token=hf_token)
            seconds = time.monotonic() - t0
            store.write_bytes(out_rel, json.dumps(result, indent=2).encode("utf-8"))
            row = {**usage_row(item, gpu, started, seconds, "ok", cu_per_hour), "output_rel": out_rel,
                   "model_size": model_size, **summarize(result)}
            if result.get("diarization_error"):
                row["diarization_error"] = redact(str(result["diarization_error"]), secrets)
            logger.success("{}: {} segments, {} speakers, {:.0f}s GPU -> {}", item, row["segments"], row["speakers"],
                           seconds, out_rel)
        except Exception as exc:  # noqa: BLE001 - one bad item never stops the batch
            row = {**usage_row(item, gpu, started, time.monotonic() - t0, "failed", cu_per_hour),
                   "model_size": model_size,
                   "error_text": redact(f"{type(exc).__name__}: {str(exc)[:200]}", secrets)}
            logger.error("{} failed: {}", item, row["error_text"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)   # Colab's disk is small; never keep audio between items
        append_usage(store, run_date, [row])
        rows.append(row)
    return rows


def _split_items(values: list[str]) -> list[str]:
    return [p for v in values for p in re.split(r"[,\n]", v)]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m llm.gpu.colab_diarize",
                                description="WhisperX speech-to-text + speaker separation on a Colab GPU (#297).")
    p.add_argument("--items", action="append", required=True,
                   help="landing-volume paths (crawl/audio/<file>) or direct media URLs; comma or newline separated")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"most items per run (default {DEFAULT_LIMIT})")
    p.add_argument("--model-size", default=DEFAULT_MODEL_SIZE, help="WhisperX model (default small)")
    p.add_argument("--run-date", default=None, help="output folder date, YYYY-MM-DD (default today, UTC); reuse it "
                   "to resume a run from an earlier day")
    p.add_argument("--volume", default=LANDING_VOLUME, help=f"landing volume (default {LANDING_VOLUME})")
    p.add_argument("--drive-root", default=DRIVE_ROOT, help="Drive folder used when no Databricks credentials are set")
    p.add_argument("--cu-per-hour", type=float, default=None,
                   help="CU/hour from Colab's Resources panel (default: the documented rate for the GPU)")
    p.add_argument("--dry-run", action="store_true", help="plan and show skips; no GPU, no writes")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_date = check_run_date(args.run_date or today_utc())
    secrets = [get_secret(n) for n in TOKEN_NAMES]
    hf_token = get_secret("HF_TOKEN")
    gpu = "T4"
    if not args.dry_run:
        from llm.usage.gpu import gpu_names

        names = gpu_names()
        if not names:
            logger.error("No GPU attached. Colab: Runtime > Change runtime type > T4 GPU, then run again.")
            return 2
        gpu = gpu_kind(names[0])
        if not hf_token:
            logger.error("No HF_TOKEN in Colab secrets or the environment (pyannote's speaker models are gated).")
            return 2
    store = make_store(args.volume, args.drive_root)
    logger.info("run {} on {} ({}), model {}, results to {} {}", run_date, PLATFORM, gpu, args.model_size,
                store.label, output_dir_rel(run_date))
    rows = run_batch(_split_items(args.items), store, run_date=run_date, limit=args.limit,
                     model_size=args.model_size, gpu=gpu, cu_per_hour=args.cu_per_hour, hf_token=hf_token,
                     secrets=secrets, volume=args.volume, dry_run=args.dry_run)
    if not args.dry_run:
        try:
            copy_gpu_run_rows(store, run_date, datetime.now(UTC).strftime("%H%M%S"))
        except Exception as exc:  # noqa: BLE001 - usage copy never fails the run
            logger.warning("gpu_run rows not copied: {}", redact(str(exc), secrets))
    print(summary_table(rows))
    return exit_code([r for r in rows if r.get("run_status_code") in ("ok", "failed")])


if __name__ == "__main__":
    sys.exit(main())
