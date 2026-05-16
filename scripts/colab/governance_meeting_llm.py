"""
Helpers for governance meeting analysis → structured JSON (policy_analysis prompt).

Designed for Google Colab: remote APIs (OpenAI-compatible or Google Gen AI with
multimodal Gemma), parse ``---DOCUMENT_BREAK---`` output, optional Orbis enrichment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


DOCUMENT_BREAK = "---DOCUMENT_BREAK---"


def load_text_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def chunk_text(
    text: str,
    max_chars: int = 14_000,
    overlap: int = 800,
) -> List[str]:
    """
    Split long transcripts into overlapping windows (character-based proxy for tokens).
    Agenda-aware splitting can replace this later (split on headings / timestamps).
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _extract_json_object(text: str) -> str:
    """Strip markdown fences and isolate outermost JSON object."""
    s = text.strip()
    if "```json" in s:
        m = re.search(r"```json\s*(.*?)\s*```", s, re.DOTALL)
        if m:
            s = m.group(1).strip()
    elif s.startswith("```"):
        lines = s.split("\n")
        if len(lines) > 2:
            s = "\n".join(lines[1:-1]).strip()
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        s = s[first : last + 1]
    return s.strip()


def parse_policy_analysis_response(raw: str) -> Dict[str, Any]:
    """
    Split model output into JSON analysis, markdown summary, optional mermaid block.

    Canonical format (see prompts/policy_analysis.md):
      JSON
      ---DOCUMENT_BREAK---
      summary markdown
      ---DOCUMENT_BREAK---
      mermaid / extra
    """
    parts = raw.split(DOCUMENT_BREAK)
    out: Dict[str, Any] = {
        "json_analysis": None,
        "summary": None,
        "extra": None,
        "raw": raw,
        "parse_error": None,
    }
    if not parts:
        return out
    try:
        json_text = _extract_json_object(parts[0])
        out["json_analysis"] = json.loads(json_text)
    except (json.JSONDecodeError, ValueError) as e:
        out["parse_error"] = str(e)
        out["json_analysis"] = {"_error": str(e), "_raw_preview": parts[0][:2000]}
    if len(parts) >= 2:
        out["summary"] = parts[1].strip()
    if len(parts) >= 3:
        out["extra"] = parts[2].strip()
    return out


@dataclass
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.1
    max_tokens: int = 8192


def call_openai_compatible_chat(
    *,
    config: OpenAICompatibleConfig,
    system_prompt: str,
    user_content: str,
) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=config.base_url, api_key=config.api_key)
    resp = client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    choice = resp.choices[0]
    if not choice.message or not choice.message.content:
        return ""
    return choice.message.content


def call_google_genai_multimodal(
    *,
    api_key: str,
    model: str,
    system_instruction: str,
    user_text: str,
    media: List[tuple[str | Path, str]],
    temperature: float = 0.1,
    max_output_tokens: int = 8192,
) -> str:
    """
    Google AI Studio / Gemini API client (``google-genai``) with one user turn:
    text ``user_text`` plus optional inline bytes (audio, PDF, images).

    ``media`` is a list of ``(path, mime_type)``; each file is read and sent as
    ``Part.from_bytes``. Keep total request size within provider limits (use the
    Files API for very long audio — not implemented here).

    Requires: ``pip install google-genai``.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    parts: List[Any] = [types.Part.from_text(text=user_text)]
    for path, mime in media:
        p = Path(path)
        parts.append(types.Part.from_bytes(data=p.read_bytes(), mime_type=mime))
    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )
    text = getattr(response, "text", None)
    if text:
        return text
    # Fallback if SDK omits .text (blocked / empty candidates)
    cands = getattr(response, "candidates", None) or []
    if not cands:
        return ""
    parts_out = getattr(cands[0].content, "parts", None) or []
    bits: List[str] = []
    for pt in parts_out:
        t = getattr(pt, "text", None)
        if t:
            bits.append(t)
    return "".join(bits)


def merge_orbis_into_organizations(
    analysis: Dict[str, Any],
    orbis_by_org_id: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enrich organizations[].financial_interest (or attach orbis_profile) from a lookup dict.

    `orbis_by_org_id` keys should match `org_id` slugs from the model output.
    Values can be any JSON-serializable structure (Orbis export shape is up to you).
    """
    if not isinstance(analysis, dict):
        return analysis
    orgs = analysis.get("organizations")
    if not isinstance(orgs, list):
        return analysis
    for row in orgs:
        if not isinstance(row, dict):
            continue
        oid = row.get("org_id")
        if not oid or oid not in orbis_by_org_id:
            continue
        payload = orbis_by_org_id[oid]
        row["orbis_profile"] = payload
        summary = json.dumps(payload, ensure_ascii=False)[:4000]
        prev = row.get("financial_interest")
        if prev:
            row["financial_interest"] = f"{prev}\n\nOrbis: {summary}"
        else:
            row["financial_interest"] = f"Orbis: {summary}"
    return analysis