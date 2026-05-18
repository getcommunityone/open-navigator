"""Colab two-phase runtime helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_COLAB = Path(__file__).resolve().parents[1] / "scripts" / "colab"
if str(_COLAB) not in sys.path:
    sys.path.insert(0, str(_COLAB))

from colab_runtime_phases import (  # noqa: E402
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
        "colab_runtime_phases.cuda_available",
        lambda: False,
    )
    assert runtime_label() == "CPU"
