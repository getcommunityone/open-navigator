"""Colab two-phase runtime helpers."""

from __future__ import annotations


from llm.governance.colab_runtime_phases import (
    colab_two_phase_enabled,
    runtime_label,
)


def test_colab_two_phase_default_on(monkeypatch) -> None:
    monkeypatch.delenv("GOVERNANCE_COLAB_TWO_PHASE", raising=False)
    assert colab_two_phase_enabled() is True
    monkeypatch.setenv("GOVERNANCE_COLAB_TWO_PHASE", "0")
    assert colab_two_phase_enabled() is False


def test_runtime_label_cpu_when_no_cuda(monkeypatch) -> None:
    monkeypatch.setattr(
        "llm.governance.colab_runtime_phases.cuda_available",
        lambda: False,
    )
    assert runtime_label() == "CPU"
