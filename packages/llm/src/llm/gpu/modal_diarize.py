"""Speech-to-text and speaker separation (WhisperX) on a Modal GPU (#314).

Runs ``llm.gemini.diarize_postprocess.diarize_audio_whisperx`` on a T4 in Modal, for audio already in the Modal volume
``open-navigator-audio`` or at a direct media URL (a city's own archive file). YouTube blocks cloud IPs
(``scrapers/youtube/BYPASS_IP_BLOCK.md``), so put YouTube audio in the volume first:
``modal volume put open-navigator-audio <file> meetings/<file>``.

    pip install modal && modal token new          # once
    modal run packages/llm/src/llm/gpu/modal_diarize.py --items meetings/a.opus --limit 3 --out data/modal_out
    # or: GitHub Actions > "GPU diarization on Modal" > Run workflow (.github/workflows/gpu-diarize-modal.yml)

Each item writes ``<name>.diarized.json`` and one row in ``usage.jsonl``: GPU, seconds, GPU-hours and an **estimated**
cost (GPU time at Modal's published rate; CPU and memory are extra, so the invoice is a little higher). A batch is
capped (``--limit``, default 3) so one run can't use the month's free credit.

The plain parts (``plan_batch``, ``estimated_cost_usd``, ``usage_row``, ``source_of``, ``output_name``) need no Modal
and are tested in ``tests/test_modal_diarize.py``.
"""

from __future__ import annotations

import json
import posixpath
import re
import time
from datetime import UTC, datetime
from pathlib import Path

APP_NAME = "open-navigator-gpu"
VOLUME_NAME = "open-navigator-audio"
VOLUME_MOUNT = "/audio"
HF_SECRET_NAME = "huggingface"      # Modal secret holding HF_TOKEN (pyannote's diarization models are gated)
DEFAULT_GPU = "T4"                  # cheapest; WhisperX "small" fits in its 16 GB
DEFAULT_LIMIT = 3
TIMEOUT_SECONDS = 3600              # one long meeting on a T4; a hung run stops here
RETRIES = 1                         # a lost or preempted GPU can pass on its own; bad audio fails again and stops

# Modal's published GPU rates, US$ per second (modal.com/pricing, as reported 2026-11-14). GPU time only.
GPU_USD_PER_SECOND = {
    "T4": 0.000164,
    "L4": 0.000222,
    "A10": 0.000306,
    "A10G": 0.000306,
    "L40S": 0.000542,
    "A100-40GB": 0.000583,
    "A100-80GB": 0.000694,
    "H100": 0.001097,
}


def plan_batch(items: list[str], limit: int = DEFAULT_LIMIT) -> list[str]:
    """Items to run: trimmed, empty and repeated ones dropped, at most ``limit`` (at least one)."""
    out: list[str] = []
    for item in items:
        item = (item or "").strip()
        if item and item not in out:
            out.append(item)
    return out[: max(1, int(limit))]


def estimated_cost_usd(seconds: float, gpu: str, rates: dict[str, float] | None = None) -> float | None:
    """GPU seconds at the published rate; None for a GPU with no rate (never a guessed figure)."""
    rate = (rates or GPU_USD_PER_SECOND).get(gpu.upper())
    return None if rate is None else float(seconds) * rate


def usage_row(item: str, gpu: str, started_ts: str, seconds: float, status_code: str) -> dict:
    """One usage row per item, in the shape of ``llm.usage`` GPU rows, marked as an estimate."""
    return {
        "platform_name": "modal",
        "step_name": "whisperx_diarization",
        "item_name": item,
        "gpu_name": gpu.upper(),
        "started_ts": started_ts,
        "duration_seconds": round(float(seconds), 3),
        "gpu_hours": float(seconds) / 3600.0,
        "estimated_cost_usd": estimated_cost_usd(seconds, gpu),
        "is_estimated": True,
        "run_status_code": status_code,
    }


def source_of(item: str) -> tuple[str, str]:
    """('url', item) for an http(s) URL, else ('volume', path inside the mounted volume)."""
    if re.match(r"^https?://", item):
        return "url", item
    path = posixpath.normpath(posixpath.join(VOLUME_MOUNT, item.lstrip("/")))
    if not path.startswith(VOLUME_MOUNT + "/"):
        raise ValueError(f"{item!r} points outside the volume {VOLUME_NAME}")
    return "volume", path


def output_name(item: str) -> str:
    """A file-safe output name for an item."""
    base = re.sub(r"^https?://[^/]+/", "", item).split("?")[0]
    base = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", base)
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_") + ".diarized.json"


# ---------------------------------------------------------------------------- Modal (only when modal is installed)
try:
    import modal
except ImportError:  # the plain parts above stay importable (tests, CI) without Modal
    modal = None

if modal is not None:
    _image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("ffmpeg")
        # the same pins as requirements-transcript-diarize.txt (numpy<2 for the torch/whisperx stack)
        .pip_install("numpy>=1.26.0,<2.0.0", "whisperx>=3.1.0", "torch>=2.0.0", "torchaudio>=2.0.0", "requests")
        .add_local_python_source("llm")
    )
    app = modal.App(APP_NAME)
    _volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

    @app.function(image=_image, gpu=DEFAULT_GPU, timeout=TIMEOUT_SECONDS, retries=RETRIES,
                  volumes={VOLUME_MOUNT: _volume}, secrets=[modal.Secret.from_name(HF_SECRET_NAME)])
    def diarize(item: str, model_size: str = "small") -> dict:
        """Run WhisperX on one item; returns {result, usage}. Never logs transcript text."""
        import tempfile

        import requests

        from llm.gemini.diarize_postprocess import diarize_audio_whisperx

        started = datetime.now(UTC).isoformat()
        t0 = time.monotonic()
        kind, where = source_of(item)
        try:
            if kind == "url":
                tmp = Path(tempfile.mkdtemp()) / "audio"
                with requests.get(where, stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with tmp.open("wb") as f:
                        for chunk in r.iter_content(1 << 20):
                            f.write(chunk)
                audio = tmp
            else:
                audio = Path(where)
            result = diarize_audio_whisperx(audio, model_size=model_size, device="cuda")
            status = "ok"
        except Exception as e:  # noqa: BLE001 - recorded on the row, then re-raised so Modal's retry applies
            usage = usage_row(item, DEFAULT_GPU, started, time.monotonic() - t0, "failed")
            usage["error_text"] = f"{type(e).__name__}: {str(e)[:200]}"
            print(json.dumps(usage))
            raise
        usage = usage_row(item, DEFAULT_GPU, started, time.monotonic() - t0, status)
        print(json.dumps(usage))   # metadata only: the run's log shows cost without the transcript
        return {"result": result, "usage": usage}

    @app.local_entrypoint()
    def main(items: str, limit: int = DEFAULT_LIMIT, out: str = "data/modal_out", model_size: str = "small"):
        """Run a batch: comma-separated items (volume paths or URLs); writes outputs and usage.jsonl to ``out``."""
        batch = plan_batch(items.split(","), limit)
        out_dir = Path(out)
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for item, res in zip(batch, diarize.map(batch, kwargs={"model_size": model_size},
                                                return_exceptions=True)):
            if isinstance(res, Exception):
                rows.append({**usage_row(item, DEFAULT_GPU, datetime.now(UTC).isoformat(), 0.0, "failed"),
                             "error_text": f"{type(res).__name__}: {str(res)[:200]}"})
                continue
            (out_dir / output_name(item)).write_text(json.dumps(res["result"], indent=2))
            rows.append(res["usage"])
        with (out_dir / "usage.jsonl").open("a") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        known = [r["estimated_cost_usd"] for r in rows if r.get("estimated_cost_usd") is not None]
        print(f"{sum(r['run_status_code'] == 'ok' for r in rows)}/{len(rows)} ok; "
              f"estimated GPU cost ${sum(known):.4f} (GPU time only; CPU and memory are extra)")
