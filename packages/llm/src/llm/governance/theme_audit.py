"""
Theme / COFOG explainability for policy_analysis outputs.

Surfaces why a decision got its primary_theme, validates COFOG table consistency,
and flags obvious keyword mismatches (e.g. parks topic labeled Civil Rights).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Mirrors prompts/policy_analysis_v1.md COFOG table.
THEME_TO_COFOG: Dict[str, str] = {
    "Fiscal and Budget Management": "COFOG-01",
    "Infrastructure and Capital Projects": "COFOG-04",
    "Zoning and Land Use": "COFOG-06",
    "Public Safety and Emergency Services": "COFOG-03",
    "Environmental and Natural Resources": "COFOG-05",
    "Housing and Community Development": "COFOG-06",
    "Economic Development and Business": "COFOG-04",
    "Transportation and Mobility": "COFOG-04",
    "Education and Workforce": "COFOG-09",
    "Health and Human Services": "COFOG-07",
    "Civil Rights and Equity": "COFOG-01",
    "Governance and Administrative Policy": "COFOG-01",
    "Parks and Recreation": "COFOG-08",
    "Utilities and Public Works": "COFOG-06",
    "Technology and Innovation": "COFOG-04",
    "Legal and Compliance": "COFOG-01",
    "Intergovernmental Relations": "COFOG-01",
    "Public Engagement and Communications": "COFOG-01",
}

_PARKS_KEYWORDS = re.compile(
    r"\b(parks?|recreation|playground|ballfield|athletic|trail|greenway|"
    r"sports complex|recreational)\b",
    re.IGNORECASE,
)


def expected_cofog_for_theme(primary_theme: str) -> Optional[str]:
    return THEME_TO_COFOG.get((primary_theme or "").strip())


def audit_decision_themes(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One audit row per decision for sidecars and consolidated summaries."""
    rows: List[Dict[str, Any]] = []
    for d in decisions:
        if not isinstance(d, dict):
            continue
        did = d.get("decision_id") or "?"
        theme = (d.get("primary_theme") or "").strip()
        cofog = (d.get("primary_theme_cofog") or "").strip()
        expected = expected_cofog_for_theme(theme)
        text = " ".join(
            str(d.get(k) or "")
            for k in ("topic", "headline", "decision_statement", "agenda_item")
        )
        issues: List[str] = []
        if theme and expected and cofog and cofog != expected:
            issues.append(
                f"COFOG table mismatch: {theme!r} maps to {expected}, not {cofog}"
            )
        if _PARKS_KEYWORDS.search(text) and theme != "Parks and Recreation":
            issues.append(
                f"Wording suggests Parks and Recreation but primary_theme is {theme!r} "
                f"({cofog}) — model may have misclassified"
            )
        rationale = (d.get("primary_theme_rationale") or "").strip()
        if not rationale:
            issues.append("Missing primary_theme_rationale — re-run Demo 3 for explainability")
        rows.append(
            {
                "decision_id": did,
                "topic": d.get("topic"),
                "primary_theme": theme,
                "primary_theme_cofog": cofog,
                "expected_cofog_for_theme": expected,
                "primary_theme_rationale": rationale or None,
                "cofog_note": (
                    f"{cofog} is correct for {theme!r} per the COFOG table"
                    if expected and cofog == expected
                    else None
                ),
                "flags": issues,
            }
        )
    return rows


def format_theme_audit_markdown(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "_No decisions to audit._\n"
    lines = [
        "## Theme & COFOG classification",
        "",
        "COFOG codes follow the fixed table in `policy_analysis_v1.md` "
        "(e.g. **Civil Rights and Equity → COFOG-01**, **Parks and Recreation → COFOG-08**). "
        "If you see COFOG-01 on a parks item, the issue is usually **primary_theme**, not the code.",
        "",
        "| ID | Topic | Primary theme | COFOG | Why (model) | Flags |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        flags = "; ".join(r.get("flags") or []) or "—"
        why = (r.get("primary_theme_rationale") or "—").replace("|", "\\|")
        topic = (r.get("topic") or "—").replace("|", "\\|")
        theme = (r.get("primary_theme") or "—").replace("|", "\\|")
        lines.append(
            f"| {r.get('decision_id')} | {topic} | {theme} | "
            f"{r.get('primary_theme_cofog') or '—'} | {why} | {flags} |"
        )
    return "\n".join(lines) + "\n"
