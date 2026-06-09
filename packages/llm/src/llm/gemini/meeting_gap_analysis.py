"""
On-demand reconciliation of an AI meeting summary against the OFFICIAL minutes.

The AI summary + decisions are derived from the meeting VIDEO transcript; the
agenda / minutes are the official human-written record. Treating the official
document as authoritative for formal facts, this asks Gemini to produce — grounded
ONLY in the supplied texts — four things:

1. ``corrections``      — facts/numbers in the AI summary the official document
                          CONTRADICTS (AI mistakes to fix from the minutes).
2. ``corrected_summary``— the AI summary rewritten with those factual corrections
                          applied (and nothing else changed).
3. ``decision_enrichments`` — for each decision, the exact ADDRESSES/locations,
                          related LEGISLATION (ordinance/resolution numbers), and
                          DOLLAR amounts/transactions stated in the official
                          document — the precise detail the video recap usually lacks.
4. ``minutes_omissions``— things discussed/decided (present in the AI recap from
                          the video) that the official document does NOT record —
                          potential selective recording / human-side bias. This is
                          the editorially interesting "raised eyebrows" signal.

This repo forbids fabricated data: the prompt is strictly grounded — every item
must quote the supplied texts; the model must never invent facts, numbers, names,
addresses, legislation, or votes. When document text could not be extracted
(empty), this module does NOT call Gemini and returns a structured marker so the
caller can render an explicit unavailable state.
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from llm.gemini.genai_text_client import (
    call_gemini_text,
    default_flash_model,
    extract_json_from_model_text,
    resolve_gemini_api_key,
)

__all__ = ["analyze_gaps"]

_LIST_KEYS = ("corrections", "minutes_omissions", "decision_enrichments")
_MAX_ITEMS = 12


def _empty_marker(status: str, overall: str, *, model: str | None = None) -> dict[str, Any]:
    """A structured result with empty collections — for no-text / failure paths."""
    return {
        "status": status,
        "corrections": [],
        "corrected_summary": "",
        "minutes_omissions": [],
        "decision_enrichments": [],
        "overall": overall,
        "model": model,
    }


def _system_instruction(document_type: str) -> str:
    return (
        "You are a civic-data analyst reconciling an AI-generated meeting summary "
        "(derived from the meeting VIDEO transcript) against the OFFICIAL "
        f"{document_type} document for the same meeting.\n\n"
        f"Treat the official {document_type} as AUTHORITATIVE for formal facts — "
        "exact numbers, dollar amounts, addresses, legislation/ordinance numbers, "
        "vote tallies, dates, and outcomes.\n\n"
        "CRITICAL grounding rule: every item you report MUST be grounded in and "
        "quote the supplied texts. NEVER invent, infer, or fabricate facts, "
        "numbers, names, addresses, legislation, votes, or outcomes. If a category "
        "has nothing, return an empty array (or empty string). Do not pad. This "
        "platform forbids fabricated data — a made-up item is worse than nothing.\n\n"
        "Return a single JSON object ONLY — no prose, no markdown fences."
    )


def _decisions_block(decisions: Optional[list[dict[str, Any]]]) -> str:
    """Render the decisions list the model should enrich, keyed by a stable id."""
    if not decisions:
        return "(no extracted decisions for this meeting)"
    lines = []
    for d in decisions:
        ref = d.get("id") or d.get("headline") or "decision"
        head = d.get("headline") or "(untitled)"
        stmt = d.get("statement") or ""
        stmt = f" — {stmt}" if stmt else ""
        lines.append(f'- id="{ref}": {head}{stmt}')
    return "\n".join(lines)


def _prompt(
    summary_text: str,
    document_text: str,
    document_type: str,
    decisions: Optional[list[dict[str, Any]]],
) -> str:
    dt = document_type
    return (
        f"Reconcile the AI MEETING SUMMARY (and decisions) against the OFFICIAL "
        f"{dt.upper()} document below.\n\n"
        "Produce these four things, each grounded ONLY in the supplied texts:\n\n"
        f"1. corrections = facts/numbers in the AI summary that the official {dt} "
        "CONTRADICTS (e.g. a wrong dollar amount, address, vote count, name, date). "
        'Each: {"quote": <verbatim from the ' + dt + '>, "ai_claim": <the AI\'s '
        'wrong statement>, "correction": <the corrected fact>}.\n\n'
        f"2. corrected_summary = the AI summary text rewritten so ONLY the factual "
        f"errors above are fixed using the {dt}; keep all other wording and "
        'structure unchanged. If there were no corrections, return "".\n\n'
        f"3. decision_enrichments = for EACH decision listed below, the precise "
        f"detail the official {dt} states that the video recap lacks: exact "
        "ADDRESSES/locations, related LEGISLATION (ordinance/resolution/bill "
        "numbers), and DOLLAR amounts/transactions. Reference the decision by its "
        'id. Each: {"decision_ref": <id>, "addresses": [..], "legislation": [..], '
        '"dollar_amounts": [{"amount": <e.g. "$45,000">, "description": <what it is>, '
        '"quote": <verbatim>}]}. Only include a decision if the ' + dt + " adds real "
        "detail for it; leave arrays empty otherwise.\n\n"
        f"4. minutes_omissions = things discussed or decided that appear in the AI "
        f"recap (from the video) but that the official {dt} does NOT record — "
        'possible selective recording. Each: {"quote": <verbatim from the AI '
        'recap>, "detail": <what the official ' + dt + " left out and why it may "
        'matter>}.\n\n'
        f"Cap each list to at most {_MAX_ITEMS} items.\n\n"
        "Return JSON ONLY with exactly these keys:\n"
        "{\n"
        '  "corrections": [{"quote": "...", "ai_claim": "...", "correction": "..."}],\n'
        '  "corrected_summary": "...",\n'
        '  "decision_enrichments": [{"decision_ref": "...", "addresses": ["..."], '
        '"legislation": ["..."], "dollar_amounts": [{"amount": "...", "description": '
        '"...", "quote": "..."}]}],\n'
        '  "minutes_omissions": [{"quote": "...", "detail": "..."}],\n'
        '  "overall": "one-paragraph plain-language summary of how well they align"\n'
        "}\n\n"
        "=== AI MEETING SUMMARY (from video transcript) ===\n"
        f"{summary_text}\n\n"
        "=== EXTRACTED DECISIONS (enrich these) ===\n"
        f"{_decisions_block(decisions)}\n\n"
        f"=== OFFICIAL {dt.upper()} DOCUMENT ===\n"
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
    decisions: Optional[list[dict[str, Any]]] = None,
    model: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Reconcile an AI meeting summary against an official agenda/minutes document.

    ``document_type`` is "agenda" or "minutes". ``decisions`` is an optional list of
    ``{"id", "headline", "statement"}`` to enrich from the document. Returns a dict
    that always carries ``status``, ``model``, ``corrections``, ``corrected_summary``,
    ``decision_enrichments``, ``minutes_omissions`` and ``overall``.

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
        user_text=_prompt(summary_text, document_text, document_type, decisions),
        system_instruction=_system_instruction(document_type),
    )

    parsed = extract_json_from_model_text(result.text)
    if not isinstance(parsed, dict):
        logger.warning("Gap analysis: model response was not JSON (model={})", result.model)
        marker = _empty_marker("parse_error", "", model=result.model)
        marker["raw"] = result.text[:2000]
        return marker

    out: dict[str, Any] = {"status": "ok", "model": result.model}
    for key in _LIST_KEYS:
        out[key] = _normalize_list(parsed.get(key))
    corrected = parsed.get("corrected_summary")
    out["corrected_summary"] = corrected if isinstance(corrected, str) else ""
    overall = parsed.get("overall")
    out["overall"] = overall if isinstance(overall, str) else ""
    return out
