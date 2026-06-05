"""
Controlled vocabulary for civic policy-decision ``primary_theme`` labels.

Single source of truth for the categorical theme assigned to each decision in the
``policy_analysis`` pipeline. This is the **cause signal** that trending-causes
rebuilds from (``int_trending_causes_by_jurisdiction`` →
``jurisdiction_state_aggregate.trending_causes``).

The vocabulary is the 18-label COFOG theme list already established in
``prompts/policy_analysis_v1.md`` and mirrored by
``llm.governance.theme_audit.THEME_TO_COFOG``. We keep the labels here as the
importable constant so the prompt, the extraction normalizer, the bronze persist
write, and the audit all agree on the exact strings. Do **not** invent new labels:
the dbt bronze layer keys off the verbatim human-readable label.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Theme label -> COFOG code. Mirrors the table in prompts/policy_analysis_v1.md.
# This is the canonical controlled vocabulary; ``theme_audit`` imports it.
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

#: Ordered list of the canonical theme labels (for prompts / UIs).
PRIMARY_THEMES: List[str] = list(THEME_TO_COFOG.keys())

# Case-insensitive lookup for tolerant normalization of model output.
_LOWER_TO_CANONICAL: Dict[str, str] = {label.lower(): label for label in PRIMARY_THEMES}


def is_valid_theme(theme: Optional[str]) -> bool:
    """True when ``theme`` is exactly one of the canonical labels."""
    return bool(theme) and theme in THEME_TO_COFOG


def normalize_primary_theme(theme: Optional[str]) -> Optional[str]:
    """
    Coerce a model-emitted theme to the canonical label, or ``None``.

    Tolerant of case/whitespace drift so a slightly off-cased label still lands on
    the controlled vocabulary. Unknown / empty values return ``None`` (the column
    is nullable by design) rather than forcing a wrong bucket.
    """
    if not theme:
        return None
    cleaned = str(theme).strip()
    if not cleaned:
        return None
    if cleaned in THEME_TO_COFOG:
        return cleaned
    return _LOWER_TO_CANONICAL.get(cleaned.lower())


def cofog_for_theme(theme: Optional[str]) -> Optional[str]:
    """COFOG code for a (possibly un-normalized) theme label, or ``None``."""
    canonical = normalize_primary_theme(theme)
    return THEME_TO_COFOG.get(canonical) if canonical else None
