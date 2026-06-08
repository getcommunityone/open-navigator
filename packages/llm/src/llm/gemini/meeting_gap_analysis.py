"""
On-demand gap analysis: AI meeting summary vs. official agenda / minutes.

Given an AI-generated meeting summary (derived from the meeting VIDEO transcript)
and the plain text of the OFFICIAL agenda or minutes document, ask Gemini to
report — grounded ONLY in the supplied texts — what the AI summary OMITTED,
where it may have ERRED, and the INTERESTING GAPS worth a citizen's attention.

This repo forbids fabricated data: the prompt is strictly grounded — every
reported item must quote the supplied texts; the model must never invent facts,
numbers, names, or votes. When document text could not be extracted (empty),
this module does NOT call Gemini and returns a structured "no document text"
marker so the caller can render an explicit unavailable state.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from llm.gemini.genai_text_client import (
    call_gemini_text,
    default_flash_model,
    extract_json_from_model_text,
    resolve_gemini_api_key,
)

__all__ = ["analyze_gaps"]

# The four content keys the caller can always rely on existing in an "ok"/marker
# result. ``status`` and ``model`` are added alongside.
_LIST_KEYS = ("omissions", "possible_errors", "interesting_gaps")
_MAX_ITEMS = 8


def _empty_marker(status: str, overall: str, *, model: str | None = None) -> dict[str, Any]:
    """A structured result with empty lists — used for no-text / failure paths."""
    return {
        "status": status,
        "omissions": [],
        "possible_errors": [],
        "interesting_gaps": [],
        "overall": overall,
        "model": model,
    }


def _system_instruction(document_type: str) -> str:
    return (
        "You are a civic-data analyst comparing an AI-generated meeting summary "
        "(derived from the meeting VIDEO transcript) against the OFFICIAL "
        f"{document_type} document for the same meeting.\n\n"
        "CRITICAL grounding rule: every item you report MUST be grounded in and "
        "quote the supplied texts. NEVER invent, infer, or fabricate facts, "
        "numbers, names, votes, or outcomes. If a category has nothing notable, "
        "return an empty array for it. Do not pad lists. This platform forbids "
        "fabricated data — a made-up item is worse than an empty list.\n\n"
        "Return a single JSON object ONLY — no prose, no markdown fences."
    )


def _prompt(summary_text: str, document_text: str, document_type: str) -> str:
    return (
        f"Compare the AI MEETING SUMMARY against the OFFICIAL {document_type.upper()} "
        "document below.\n\n"
        "Definitions:\n"
        f"- omissions = items present in the official {document_type} but MISSING "
        "from the AI summary.\n"
        f"- possible_errors = claims in the AI summary that the {document_type} "
        "appears to CONTRADICT.\n"
        "- interesting_gaps = notable differences worth a citizen's attention.\n\n"
        f"Cap each list to at most {_MAX_ITEMS} items. Every list item needs a "
        '"quote" (verbatim from one of the supplied texts) and a "detail" '
        "(plain-language explanation). If a list has nothing, return [].\n\n"
        "Return JSON ONLY with exactly these keys:\n"
        "{\n"
        '  "omissions": [{"quote": "...", "detail": "..."}],\n'
        '  "possible_errors": [{"quote": "...", "detail": "..."}],\n'
        '  "interesting_gaps": [{"quote": "...", "detail": "..."}],\n'
        '  "overall": "one-paragraph plain-language summary of how well they align"\n'
        "}\n\n"
        "=== AI MEETING SUMMARY (from video transcript) ===\n"
        f"{summary_text}\n\n"
        f"=== OFFICIAL {document_type.upper()} DOCUMENT ===\n"
        f"{document_text}\n"
    )


def _normalize_list(value: Any) -> list[Any]:
    """Coerce a model value to a list, capped at _MAX_ITEMS. Non-lists → []."""
    if not isinstance(value, list):
        return []
    return value[:_MAX_ITEMS]


def analyze_gaps(
    *,
    summary_text: str,
    document_text: str,
    document_type: str,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Compare an AI meeting summary against an official agenda/minutes document.

    ``document_type`` is "agenda" or "minutes". Returns a dict that always carries
    ``status``, ``model``, the three lists (``omissions``, ``possible_errors``,
    ``interesting_gaps``) and ``overall``.

    Statuses:
    - ``"no_document_text"`` — ``document_text`` (or ``summary_text``) was empty;
      Gemini is NOT called.
    - ``"ok"`` — the model returned parseable JSON (normalized).
    - ``"parse_error"`` — the model response was not valid JSON; ``raw`` carries a
      truncated copy for debugging.
    """
    # DEFENSIVE: extraction failed (empty document) or no summary — never bill a
    # Gemini call we already know cannot produce a grounded comparison.
    if not (document_text or "").strip():
        return _empty_marker(
            "no_document_text", "Could not extract text from this document."
        )
    if not (summary_text or "").strip():
        return _empty_marker(
            "no_document_text", "No AI meeting summary was available to compare."
        )

    resolved_model = (model or default_flash_model()).strip()
    resolved_key = api_key or resolve_gemini_api_key()

    result = call_gemini_text(
        api_key=resolved_key,
        model=resolved_model,
        user_text=_prompt(summary_text, document_text, document_type),
        system_instruction=_system_instruction(document_type),
    )

    parsed = extract_json_from_model_text(result.text)
    if not isinstance(parsed, dict):
        logger.warning("Gap analysis: model response was not JSON (model={})", result.model)
        return {
            "status": "parse_error",
            "omissions": [],
            "possible_errors": [],
            "interesting_gaps": [],
            "overall": "",
            "model": result.model,
            "raw": result.text[:2000],
        }

    out: dict[str, Any] = {"status": "ok", "model": result.model}
    for key in _LIST_KEYS:
        out[key] = _normalize_list(parsed.get(key))
    overall = parsed.get("overall")
    out["overall"] = overall if isinstance(overall, str) else ""
    return out
