"""Demo 4: Gemma-first model pick and Opus-before-video ingest order."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_COLAB = Path(__file__).resolve().parents[1] / "scripts" / "colab"
if str(_COLAB) not in sys.path:
    sys.path.insert(0, str(_COLAB))

from governance_meeting_llm import (  # noqa: E402
    _demo4_allow_31b_audio,
    _demo4_model_preference_order,
    demo4_prefer_gemma_for_audio,
    demo4_prefer_opus_chunks,
    demo4_uses_huggingface,
    iter_demo4_ingest_strategies,
    model_accepts_demo4_audio_chunks,
    pick_demo4_model_from_available,
    resolve_demo4_model,
    resolve_drift_model,
)


def test_demo4_hf_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOVERNANCE_DEMO4_USE_HF", raising=False)
    assert demo4_uses_huggingface() is True


def test_resolve_demo4_model_uses_hf_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_DEMO4_USE_HF", "1")
    monkeypatch.setenv("GOVERNANCE_DEMO4_HF_MODEL", "google/gemma-4-E2B-it")
    assert resolve_demo4_model("gemma-4-26b-a4b-it") == "google/gemma-4-E2B-it"


def test_prefer_gemma_defaults_on() -> None:
    os.environ.pop("GOVERNANCE_DEMO4_PREFER_GEMMA_AUDIO", None)
    assert demo4_prefer_gemma_for_audio() is True


def test_allow_31b_when_prefer_gemma(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_DEMO4_PREFER_GEMMA_AUDIO", "1")
    monkeypatch.delenv("GOVERNANCE_DEMO4_ALLOW_31B_AUDIO", raising=False)
    assert _demo4_allow_31b_audio() is True
    assert model_accepts_demo4_audio_chunks("gemma-4-31b-it") is True


def test_drift_model_stays_on_hf_when_demo4_hf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_DEMO4_USE_HF", "1")
    model, use_hf = resolve_drift_model("google/gemma-4-E2B-it", thinking_model="gemma-4-31b-it")
    assert use_hf is True
    assert "E2B" in model


def test_drift_model_not_hf_repo_on_google(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_DEMO4_USE_HF", "0")
    model, use_hf = resolve_drift_model("google/gemma-4-E2B-it", thinking_model="gemma-4-31b-it")
    assert use_hf is False
    assert model == "gemma-4-31b-it"


def test_a4b_audio_when_try_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from governance_meeting_llm import (  # noqa: E402
        _demo4_allow_a4b_audio,
        model_supports_audio_video_input,
    )

    monkeypatch.setenv("GOVERNANCE_DEMO4_TRY_A4B_AUDIO", "1")
    assert _demo4_allow_a4b_audio() is True
    assert model_supports_audio_video_input("gemma-4-26b-a4b-it") is True
    monkeypatch.setenv("GOVERNANCE_DEMO4_TRY_A4B_AUDIO", "0")
    assert model_supports_audio_video_input("gemma-4-26b-a4b-it") is False


def test_block_31b_when_explicitly_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_DEMO4_ALLOW_31B_AUDIO", "0")
    assert model_accepts_demo4_audio_chunks("gemma-4-31b-it") is False


def test_pick_demo4_prefers_gemma_over_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_DEMO4_USE_HF", "0")
    monkeypatch.setenv("GOVERNANCE_DEMO4_PREFER_GEMMA_AUDIO", "1")
    monkeypatch.delenv("GOVERNANCE_DEMO4_MODEL", raising=False)
    picked = pick_demo4_model_from_available(
        ["gemini-2.0-flash", "gemma-4-31b-it"],
        thinking_model="gemma-4-31b-it",
    )
    assert picked == "gemma-4-31b-it"


def test_model_order_gemini_first_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOVERNANCE_DEMO4_PREFER_GEMMA_AUDIO", "0")
    avail = {"gemini-2.0-flash", "gemma-4-31b-it"}
    order = [m for m in _demo4_model_preference_order(avail) if m in avail]
    assert order.index("gemini-2.0-flash") < order.index("gemma-4-31b-it")


def test_resolve_drift_uses_thinking_not_hf_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOVERNANCE_DRIFT_MODEL", raising=False)
    monkeypatch.setenv("GOVERNANCE_DRIFT_USE_HF", "0")
    monkeypatch.setenv("GOVERNANCE_DEMO4_USE_HF", "1")
    mid, use_hf = resolve_drift_model("google/gemma-4-E2B-it", thinking_model="gemma-4-31b-it")
    assert mid == "gemma-4-31b-it"
    assert use_hf is False


def test_resolve_transcription_hf_only_e2b(monkeypatch: pytest.MonkeyPatch) -> None:
    from gemma_hf_backend import resolve_transcription_hf_model

    monkeypatch.setenv("GOVERNANCE_TRANSCRIPTION_HF_MODEL", "gemma-4-31b-it")
    assert resolve_transcription_hf_model() == "google/gemma-4-E2B-it"


def test_iter_demo4_opus_label_before_video(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without ffmpeg, only strategy *labels* are checked via a stubbed Opus path."""
    monkeypatch.setenv("GOVERNANCE_DEMO4_PREFER_OPUS", "1")
    monkeypatch.setenv("GOVERNANCE_DEMO4_VIDEO_CHUNKS", "1")
    fake_mp4 = tmp_path / "meet.mp4"
    fake_mp4.write_bytes(b"\x00")
    opus_chunk = tmp_path / "meet_chunk_000.opus"
    opus_chunk.write_bytes(b"\x00")
    fake_chunks = [(opus_chunk, "audio/opus")]

    import governance_meeting_llm as gml

    def _fake_chunk(*_a, **_k):
        return fake_chunks

    monkeypatch.setattr(gml, "_chunk_audio_segments", _fake_chunk)
    monkeypatch.setattr(
        gml,
        "_chunk_video_ffmpeg",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("skip video")),
    )

    labels = [
        label
        for label, _ in iter_demo4_ingest_strategies(
            fake_mp4,
            out_dir=tmp_path / "scratch",
            demo4_model="gemini-2.0-flash",
        )
    ]
    assert labels[0] == "opus_15min"
    assert demo4_prefer_opus_chunks() is True
