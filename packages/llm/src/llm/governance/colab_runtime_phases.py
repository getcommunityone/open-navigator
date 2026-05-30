"""
Colab two-phase runtime helpers: CPU for PDF/API work, GPU for Demo 4 (HF + ffmpeg).

Used by ``02_run_meeting_llm.ipynb`` §6 — not required for local runs.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def colab_two_phase_enabled() -> bool:
    """Notebook §6 runs PDF on CPU, then video on GPU (default on)."""
    return os.environ.get("GOVERNANCE_COLAB_TWO_PHASE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def runtime_label() -> str:
    if cuda_available():
        try:
            import torch

            return f"GPU ({torch.cuda.get_device_name(0)})"
        except Exception:
            return "GPU"
    return "CPU"


def ensure_cpu_runtime(*, phase: str = "PDFs, gatekeeper, Demo 3") -> None:
    """Raise if Colab is on a GPU runtime (phase 1 should use CPU)."""
    if cuda_available():
        raise RuntimeError(
            f"\n{'=' * 60}\n"
            f"Phase 1 ({phase}) must run on a **CPU** runtime.\n\n"
            "1. Runtime → Change runtime type → **CPU** (standard)\n"
            "2. Runtime → **Restart session**\n"
            "3. Re-run **§1 → §5**, then **§6 Phase 1** only\n"
            f"{'=' * 60}\n"
        )
    print(f"✓ Phase 1 runtime: {runtime_label()} (expected CPU)")


def confirm_gpu_for_demo4(*, interactive: bool = True) -> None:
    """
    Block until the user confirms a GPU runtime for Demo 4 / video.

    Set ``GOVERNANCE_COLAB_SKIP_GPU_CONFIRM=1`` to skip the prompt (CI / advanced).
    """
    if os.environ.get("GOVERNANCE_COLAB_SKIP_GPU_CONFIRM", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        if not cuda_available():
            print(
                "⚠ GOVERNANCE_COLAB_SKIP_GPU_CONFIRM=1 but no GPU detected — "
                "Demo 4 HF will likely fail."
            )
        else:
            print(f"✓ Phase 2 runtime: {runtime_label()} (confirm skipped)")
        return

    if not cuda_available():
        msg = (
            "\nNo GPU detected.\n\n"
            "1. Finish **§6 Phase 1** on CPU (PDF outputs saved to Drive).\n"
            "2. Runtime → Change runtime type → **L4 GPU** (or T4), **High RAM** if offered\n"
            "3. Runtime → **Restart session**\n"
            "4. Re-run **§1 → §5**, then **§6 Phase 2** (confirm + run)\n"
        )
        if not interactive:
            raise RuntimeError(msg)
        answer = input(msg + "\nType YES to continue on CPU anyway (likely fails): ")
        if answer.strip().upper() != "YES":
            raise RuntimeError("Stopped — connect a GPU runtime first.")
        return

    print(f"Detected: {runtime_label()}")
    if interactive:
        answer = input(
            "\n**Phase 2 — video / Demo 4 (Hugging Face E2B on GPU)**\n\n"
            "Confirm:\n"
            "  • Phase 1 finished (PDF / Demo 3 on Drive), and\n"
            "  • You switched to **GPU + High RAM** and restarted (Runtime → Change runtime type).\n"
            "  • You re-ran **§1 → §5** after the restart.\n\n"
            "Type YES to run Phase 2: "
        )
        if answer.strip().upper() != "YES":
            raise RuntimeError(
                "Stopped — complete Phase 1 on CPU, switch to GPU, re-run §1–§5, then Phase 2."
            )
    print(f"✓ Phase 2 runtime: {runtime_label()}")


def apply_media_scope_for_phase(media_key: str, namespace: Optional[Dict[str, Any]] = None) -> Any:
    """Set ``GOVERNANCE_PIPELINE_MEDIA_SCOPE`` and optional notebook globals."""
    from .pipeline_media_scope import apply_media_scope

    key = (media_key or "all").strip().lower()
    os.environ["GOVERNANCE_PIPELINE_MEDIA_SCOPE"] = key
    cfg = apply_media_scope(key)
    if namespace is not None:
        namespace["ACTIVE_MEDIA"] = cfg
        namespace["_media"] = key
    print(f"Pipeline media scope → {cfg.label} ({key!r})")
    return cfg


def print_after_video_cpu_recommendation() -> None:
    print(
        "\n"
        "=" * 60 + "\n"
        "Phase 2 complete — **switch back to CPU** (recommended)\n"
        "=" * 60 + "\n"
        "GPU sessions disconnect more often during peak hours. You do not need GPU for:\n"
        "  • optional §7–§9 reruns that only touch Google API text\n"
        "  • safety review, browsing Drive outputs, or judging summaries\n\n"
        "1. Runtime → Change runtime type → **CPU**\n"
        "2. Runtime → Restart session (optional)\n"
        "3. Open outputs on Drive under `03_processed_outputs/` and `03_human_summaries/`\n"
        "   (`GOVERNANCE_FORCE_REPROCESS=0` reuses work if you re-run later)\n"
    )
