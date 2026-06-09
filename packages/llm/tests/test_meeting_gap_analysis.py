"""Unit tests for meeting gap analysis + bytes document-text extraction.

No network: the Gemini call is monkeypatched to return a TextGenAIResult-like
object. No disk: documents are passed as in-memory bytes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from llm.gemini import meeting_gap_analysis as mga
from llm.gemini.document_text import extract_text_from_bytes


@dataclass
class _FakeResult:
    """Mimics genai_text_client.TextGenAIResult (.text / .model)."""

    text: str
    model: str = "gemini-2.5-flash"
    raw_response: object = None


# --------------------------------------------------------------------------
# analyze_gaps
# --------------------------------------------------------------------------
def test_empty_document_text_returns_marker_without_calling_gemini(monkeypatch):
    called = {"n": 0}

    def _boom(*args, **kwargs):  # pragma: no cover - must never run
        called["n"] += 1
        raise AssertionError("Gemini must not be called when document_text is empty")

    monkeypatch.setattr(mga, "call_gemini_text", _boom)

    result = mga.analyze_gaps(
        summary_text="The council approved the budget.",
        document_text="   ",
        document_type="minutes",
        api_key="test-key",
    )

    assert called["n"] == 0
    assert result["status"] == "no_document_text"
    assert result["model"] is None
    assert result["corrections"] == []
    assert result["minutes_omissions"] == []
    assert result["decision_enrichments"] == []
    assert result["corrected_summary"] == ""
    assert "Could not extract" in result["overall"]


def test_empty_summary_text_returns_marker_without_calling_gemini(monkeypatch):
    monkeypatch.setattr(
        mga,
        "call_gemini_text",
        lambda *a, **k: pytest.fail("Gemini must not be called when summary is empty"),
    )
    result = mga.analyze_gaps(
        summary_text="",
        document_text="Official minutes: item 1 approved 5-0.",
        document_type="minutes",
        api_key="test-key",
    )
    assert result["status"] == "no_document_text"


def test_valid_json_response_normalizes_to_ok(monkeypatch):
    payload = {
        "corrections": [
            {
                "quote": "appropriated $45,000",
                "ai_claim": "the council spent about $40,000",
                "correction": "the amount was $45,000",
            }
        ],
        "corrected_summary": "AI summary: budget of $45,000 passed 4-1.",
        "decision_enrichments": [
            {
                "decision_ref": "dec-1",
                "addresses": ["2100 21st Ave E"],
                "legislation": ["Resolution 2024-15"],
                "dollar_amounts": [
                    {"amount": "$45,000", "description": "training budget", "quote": "appropriated $45,000"}
                ],
            }
        ],
        "minutes_omissions": [{"quote": "public comment on noise", "detail": "Not recorded in minutes"}],
        "overall": "Mostly aligned with a couple gaps.",
        "extra_ignored_key": "should be dropped",
    }
    captured = {}

    def _fake_call(*, api_key, model, user_text, system_instruction="", **kwargs):
        captured["api_key"] = api_key
        captured["model"] = model
        captured["user_text"] = user_text
        captured["system_instruction"] = system_instruction
        return _FakeResult(text="```json\n" + json.dumps(payload) + "\n```", model=model)

    monkeypatch.setattr(mga, "call_gemini_text", _fake_call)

    result = mga.analyze_gaps(
        summary_text="AI summary: budget passed unanimously.",
        document_text="Minutes: Resolution 2024-15 approved by a vote of 4-1.",
        document_type="minutes",
        decisions=[{"id": "dec-1", "headline": "Training budget", "statement": "..."}],
        model="gemini-2.5-flash",
        api_key="test-key",
    )

    assert result["status"] == "ok"
    assert result["model"] == "gemini-2.5-flash"
    assert result["corrections"] == payload["corrections"]
    assert result["corrected_summary"] == payload["corrected_summary"]
    assert result["decision_enrichments"] == payload["decision_enrichments"]
    assert result["minutes_omissions"] == payload["minutes_omissions"]
    assert result["overall"] == "Mostly aligned with a couple gaps."
    assert "extra_ignored_key" not in result
    # The official document_type + the decision id made it into the grounded prompt.
    assert "MINUTES" in captured["user_text"]
    assert "dec-1" in captured["user_text"]
    assert "minutes" in captured["system_instruction"]
    assert captured["api_key"] == "test-key"


def test_list_cap_applied(monkeypatch):
    payload = {
        "corrections": [{"quote": str(i), "ai_claim": "a", "correction": "c"} for i in range(20)],
        "minutes_omissions": "not-a-list",  # malformed → coerced to []
        "decision_enrichments": [],
        "corrected_summary": 999,  # malformed → coerced to ""
        "overall": 12345,  # malformed → coerced to ""
    }
    monkeypatch.setattr(
        mga,
        "call_gemini_text",
        lambda **k: _FakeResult(text=json.dumps(payload), model="m"),
    )
    result = mga.analyze_gaps(
        summary_text="s",
        document_text="d",
        document_type="agenda",
        api_key="k",
    )
    assert result["status"] == "ok"
    assert len(result["corrections"]) == mga._MAX_ITEMS  # capped
    assert result["minutes_omissions"] == []
    assert result["corrected_summary"] == ""
    assert result["overall"] == ""


def test_non_json_response_returns_parse_error(monkeypatch):
    monkeypatch.setattr(
        mga,
        "call_gemini_text",
        lambda **k: _FakeResult(text="I'm sorry, I cannot do that.", model="gemini-2.5-flash"),
    )
    result = mga.analyze_gaps(
        summary_text="summary",
        document_text="official document text",
        document_type="agenda",
        api_key="test-key",
    )
    assert result["status"] == "parse_error"
    assert result["model"] == "gemini-2.5-flash"
    assert result["corrections"] == []
    assert result["minutes_omissions"] == []
    assert result["corrected_summary"] == ""
    assert result["overall"] == ""
    assert "raw" in result and "cannot do that" in result["raw"]


def test_default_model_used_when_none(monkeypatch):
    seen = {}

    def _fake_call(**kwargs):
        seen["model"] = kwargs["model"]
        return _FakeResult(text="{}", model=kwargs["model"])

    monkeypatch.setattr(mga, "call_gemini_text", _fake_call)
    monkeypatch.setattr(mga, "resolve_gemini_api_key", lambda *a, **k: "resolved-key")

    result = mga.analyze_gaps(
        summary_text="s", document_text="d", document_type="minutes"
    )
    assert seen["model"] == mga.default_flash_model()
    # Empty {} parses as a dict → ok with empty defaults.
    assert result["status"] == "ok"
    assert result["corrections"] == []
    assert result["corrected_summary"] == ""


# --------------------------------------------------------------------------
# extract_text_from_bytes
# --------------------------------------------------------------------------
def test_html_bytes_stripped():
    html = (
        b"<html><head><style>.x{color:red}</style></head>"
        b"<body><nav>menu</nav><p>Council approved the budget.</p>"
        b"<footer>copyright</footer></body></html>"
    )
    text = extract_text_from_bytes(html, url="http://x/agenda.html", content_type="text/html")
    assert "Council approved the budget." in text
    # script/style/nav/footer stripped
    assert "menu" not in text
    assert "copyright" not in text
    assert "color:red" not in text


def test_plain_text_bytes():
    text = extract_text_from_bytes(
        b"Just some minutes text.", url="http://x/file.txt", content_type="text/plain"
    )
    assert text == "Just some minutes text."


def test_empty_bytes_returns_empty():
    assert extract_text_from_bytes(b"", url="http://x/a.pdf", content_type="application/pdf") == ""


def test_garbage_pdf_does_not_raise():
    # Magic bytes claim PDF but the body is junk → fitz fails → '' (no raise).
    result = extract_text_from_bytes(
        b"%PDF-1.4 not really a pdf at all \x00\x01\x02",
        url="http://x/broken.pdf",
        content_type="application/pdf",
    )
    assert result == ""


def test_legacy_doc_unsupported():
    assert (
        extract_text_from_bytes(
            b"\xd0\xcf\x11\xe0garbage", url="http://x/old.doc", content_type="application/msword"
        )
        == ""
    )


def test_kind_inferred_from_url_extension_when_no_content_type():
    html = b"<html><body><p>Hello world</p></body></html>"
    text = extract_text_from_bytes(html, url="http://x/page.htm", content_type=None)
    assert "Hello world" in text
