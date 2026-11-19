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
- **Volume I/O:** shared helpers in ``llm.gpu.colab_io`` (#518) — Databricks Files API or a mounted Google Drive folder.
  Tokens are never printed or logged.

A paid GPU run starts only on the owner's explicit yes for that run (``AGENTS.md``, "GPU and paid compute").
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from llm.gpu import colab_io
from llm.gpu.colab_io import (
    COLAB_CU_PER_HOUR,
    COLAB_USD_PER_CU,
    DRIVE_ROOT,
    LANDING_VOLUME,
    Store,
    check_run_date,
    clean_rel,
    estimated_compute_units,
    get_secret,
    gpu_kind,
    make_store,
    measured_batch_cu,
    redact,
    today_utc,
)
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

# Re-exported for tests / notebook callers that still import stores from this module (#518).
LocalStore = colab_io.LocalStore
DatabricksVolumeStore = colab_io.DatabricksVolumeStore

PLATFORM = "colab"
DIARIZED_DIR = "diarized"
USAGE_FILE = "usage.jsonl"
SECRET_NAMES = ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "HF_TOKEN")
TOKEN_NAMES = ("DATABRICKS_TOKEN", "HF_TOKEN")

# Re-export for callers / tests that imported these from this module before #518.
volume_rel = clean_rel


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
