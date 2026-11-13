"""One usage row per GPU step (#262).

``nvidia-smi``'s own loop samples each GPU's utilization, memory and power to a
CSV while the step runs; the step's row is its wall time, GPU-hours (wall time
by GPU count, as a cloud bills), mean utilization, peak memory and energy. The
same method as health-transformation-lab-nlp (``start_gpu_sampler`` /
``gpu_stats`` there).

    with gpu_run("whisperx_diarization", video_id=video_id):
        ...

On a machine with no ``nvidia-smi`` (or ``device="cpu"``) nothing is recorded
and nothing fails.
"""

from __future__ import annotations

import csv
import shutil
import socket
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from llm.usage.calls import (
    append_row,
    current_context,
    run_id,
    usage_enabled,
    usage_log_dir,
)

SAMPLE_HEADER = "timestamp,gpu_index,utilization_pct,memory_used_mb,power_w"
_NVIDIA_SMI_TIME = "%Y/%m/%d %H:%M:%S.%f"


def gpu_names() -> list[str]:
    """Each GPU's name as ``nvidia-smi`` reports it; ``[]`` with no GPU or no tool."""
    if shutil.which("nvidia-smi") is None:
        return []
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def start_gpu_sampler(path: Path, interval_ms: int = 5000) -> tuple[subprocess.Popen, Any]:
    """Start ``nvidia-smi`` writing one line per GPU every ``interval_ms`` to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = open(path, "w", encoding="utf-8")  # noqa: SIM115 - closed by stop_gpu_sampler
    out.write(SAMPLE_HEADER + "\n")
    out.flush()
    proc = subprocess.Popen(
        [
            "nvidia-smi",
            "--query-gpu=timestamp,index,utilization.gpu,memory.used,power.draw",
            "--format=csv,noheader,nounits",
            "-lms",
            str(interval_ms),
        ],
        stdout=out,
        stderr=subprocess.DEVNULL,
    )
    return proc, out


def stop_gpu_sampler(sampler: tuple[subprocess.Popen, Any]) -> None:
    proc, out = sampler
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:  # noqa: BLE001 - a sampler that won't stop never fails the step
        proc.kill()
    finally:
        out.close()


def gpu_stats(samples: Path, start_unix: float, end_unix: float) -> dict[str, Any] | None:
    """Mean utilization, peak memory and energy from the samples between two times.

    ``nvidia-smi`` stamps samples in the machine's local time, so they are read as
    local time. Energy is each GPU's mean power over the step's time, summed over
    the GPUs; it is ``None`` when the GPU reports no power draw. ``None`` overall
    when no sample falls inside the window.
    """
    if not Path(samples).exists():
        return None
    rows: list[tuple[float, int, float, float, float | None]] = []
    with open(samples, encoding="utf-8") as fh:
        for r in csv.reader(fh):
            if not r or r[0].startswith("timestamp"):
                continue
            try:
                ts = datetime.strptime(r[0].strip(), _NVIDIA_SMI_TIME).timestamp()
                index, util, mem = int(r[1]), float(r[2]), float(r[3])
            except (ValueError, IndexError):  # a cut-off last line
                continue
            try:
                watts: float | None = float(r[4])
            except (ValueError, IndexError):  # "[N/A]" power on some GPUs
                watts = None
            rows.append((ts, index, util, mem, watts))
    inside = [r for r in rows if start_unix <= r[0] <= end_unix]
    if not inside:
        return None
    power: dict[int, list[float]] = {}
    for _, index, _, _, watts in inside:
        if watts is not None:
            power.setdefault(index, []).append(watts)
    hours = max(end_unix - start_unix, 0.0) / 3600
    energy = (
        round(sum(sum(w) / len(w) for w in power.values()) * hours, 4) if power else None
    )
    return {
        "gpu_sample_count": len(inside),
        "avg_gpu_utilization_pct": round(sum(r[2] for r in inside) / len(inside), 2),
        "max_gpu_memory_used_mb": max(r[3] for r in inside),
        "energy_wh": energy,
    }


@contextmanager
def gpu_run(
    step_name: str,
    *,
    device: str | None = None,
    interval_ms: int = 5000,
    **labels: Any,
) -> Iterator[None]:
    """Record one GPU step. A no-op when recording is off, ``device`` is ``"cpu"``,
    or the machine has no ``nvidia-smi``. An exception in the step still writes
    the row (the GPU time was spent) and is re-raised."""
    names = [] if (device or "").strip().lower() == "cpu" or not usage_enabled() else gpu_names()
    if not names:
        yield
        return
    gpu_run_id = str(uuid.uuid4())
    samples = usage_log_dir() / "gpu_samples" / f"{gpu_run_id}.csv"
    sampler = None
    try:
        sampler = start_gpu_sampler(samples, interval_ms=interval_ms)
    except Exception as exc:  # noqa: BLE001 - sampling never blocks the step
        logger.warning("GPU sampler not started for {}: {}", step_name, exc)
    started = datetime.now(UTC)
    start_unix = time.time()
    try:
        yield
    finally:
        end_unix = time.time()
        try:
            if sampler is not None:
                stop_gpu_sampler(sampler)
            wall = end_unix - start_unix
            context = current_context()
            context.update({k: str(v) for k, v in labels.items() if v})
            row: dict[str, Any] = {
                "gpu_run_id": gpu_run_id,
                "step_name": step_name,
                "started_at": started.isoformat(),
                "ended_at": datetime.now(UTC).isoformat(),
                "wall_seconds": round(wall, 1),
                "gpu_count": len(names),
                "gpu_name": names[0],
                "gpu_hours": round(wall / 3600 * len(names), 5),
                "gpu_sample_count": None,
                "avg_gpu_utilization_pct": None,
                "max_gpu_memory_used_mb": None,
                "energy_wh": None,
                "video_id": context.get("video_id"),
                "jurisdiction_id": context.get("jurisdiction_id"),
                "run_id": run_id(),
                "host_name": socket.gethostname(),
            }
            row.update(gpu_stats(samples, start_unix, end_unix) or {})
            append_row("gpu_runs", row, when=started)
            logger.info(
                "gpu step {}: {:.0f}s on {} x {} ({} GPU-hours), util {}%, peak {} MB",
                step_name,
                wall,
                len(names),
                names[0],
                row["gpu_hours"],
                row["avg_gpu_utilization_pct"],
                row["max_gpu_memory_used_mb"],
            )
        except Exception as exc:  # noqa: BLE001 - usage logging never breaks a run
            logger.warning("GPU usage row skipped for {}: {}", step_name, exc)
