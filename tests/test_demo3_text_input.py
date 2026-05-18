"""Demo 3 text-first input helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_COLAB = Path(__file__).resolve().parents[1] / "scripts" / "colab"
if str(_COLAB) not in sys.path:
    sys.path.insert(0, str(_COLAB))

from governance_meeting_llm import (  # noqa: E402
    demo3_input_mode,
    demo3_text_first_enabled,
    truncate_demo3_document_text,
)


@pytest.mark.parametrize(
    "env,expected",
    [
        ("auto", "auto"),
        ("text", "text"),
        ("text_only", "text"),
        ("vision", "vision"),
        ("full_pdf", "vision"),
        ("", "auto"),
    ],
)
def test_demo3_input_mode(monkeypatch, env: str, expected: str) -> None:
    if env:
        monkeypatch.setenv("GOVERNANCE_DEMO3_INPUT", env)
    else:
        monkeypatch.delenv("GOVERNANCE_DEMO3_INPUT", raising=False)
    assert demo3_input_mode() == expected


def test_demo3_text_first_enabled(monkeypatch) -> None:
    monkeypatch.setenv("GOVERNANCE_DEMO3_INPUT", "vision")
    assert demo3_text_first_enabled() is False
    monkeypatch.setenv("GOVERNANCE_DEMO3_INPUT", "auto")
    assert demo3_text_first_enabled() is True


def test_truncate_demo3_document_text() -> None:
    out = truncate_demo3_document_text("x" * 100, max_chars=20)
    assert len(out) <= 80
    assert "truncated" in out
    assert truncate_demo3_document_text("short", max_chars=20) == "short"
