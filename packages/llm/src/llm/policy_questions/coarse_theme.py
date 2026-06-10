"""
Coarse theme normalizer — collapse the noisy free-text ``primary_theme`` into a
stable partition for clustering.

The ``event_decision`` data carries ~284 distinct free-text themes ("Land Use",
"Zoning and Land Use", "Land Use and Zoning", "Public Safety", ...) produced by an
older prompt that predates the controlled 18-label COFOG vocabulary in
``llm.gemini.policy_themes``. Partitioning HDBSCAN by the raw label would fragment
recurring families (e.g. rezonings split across three "land use" spellings), so we
first map each raw theme to one of the canonical COFOG buckets via deterministic
keyword rules. Unmatched values fall to ``__unthemed__`` (clustered on embeddings
alone). This is the *partition* only; the precise CAP ``topic_code`` is assigned
per question by the labeler.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from llm.gemini.policy_themes import THEME_TO_COFOG, normalize_primary_theme

UNTHEMED = "__unthemed__"

# Ordered (keywords, canonical_theme). First keyword hit wins, so more specific
# buckets (zoning/land-use, housing) precede generic ones (economic development,
# governance). All canonical targets are keys of THEME_TO_COFOG.
_RULES: List[Tuple[Tuple[str, ...], str]] = [
    (("zoning", "rezon", "land use", "variance", "subdivision", "plat", "annex",
      "setback", "easement", "parcel", "site plan"), "Zoning and Land Use"),
    (("housing", "affordable", "homeless", "shelter", "tenant"), "Housing and Community Development"),
    (("police", "fire", "public safety", "emergency", "ems", "ambulance", "crime",
      "law enforcement", "disaster", "911"), "Public Safety and Emergency Services"),
    (("transport", "transit", "traffic", "mobility", "street", "sidewalk", "road",
      "highway", "parking", "pedestrian"), "Transportation and Mobility"),
    (("water", "sewer", "stormwater", "utility", "utilities", "wastewater",
      "drainage", "public works"), "Utilities and Public Works"),
    (("infrastructure", "capital", "construction", "facility", "building project",
      "bridge", "dam"), "Infrastructure and Capital Projects"),
    (("environment", "natural resource", "sustainab", "conservation", "climate",
      "pollution", "tree", "wetland"), "Environmental and Natural Resources"),
    (("park", "recreation", "library", "arts", "culture", "museum", "trail",
      "festival"), "Parks and Recreation"),
    (("education", "school", "workforce", "student", "teacher", "college"), "Education and Workforce"),
    (("health", "human services", "social services", "senior", "welfare", "mental",
      "opioid", "medicaid"), "Health and Human Services"),
    (("budget", "fiscal", "finance", "tax", "audit", "appropriat", "millage",
      "revenue", "bond"), "Fiscal and Budget Management"),
    (("economic", "business", "development", "downtown", "tourism", "incentive",
      "redevelopment"), "Economic Development and Business"),
    (("technology", "innovation", "broadband", "cyber", "digital", "software"), "Technology and Innovation"),
    (("civil right", "equity", "diversity", "inclusion", "discrimination"), "Civil Rights and Equity"),
    (("intergovern", "regional", "county board", "state legislat"), "Intergovernmental Relations"),
    (("legal", "complian", "litigation", "ordinance review", "lawsuit"), "Legal and Compliance"),
    (("engagement", "communication", "outreach", "public comment", "transparency"),
     "Public Engagement and Communications"),
    (("governance", "administ", "personnel", "operations", "policy", "charter",
      "election", "appointment", "council rule", "government"), "Governance and Administrative Policy"),
]


def coarse_theme(raw: Optional[str]) -> str:
    """Map a raw free-text theme to a canonical COFOG bucket, or ``__unthemed__``."""
    if not raw:
        return UNTHEMED
    # Exact / case-normalized hit against the controlled vocabulary first.
    exact = normalize_primary_theme(raw)
    if exact:
        return exact
    text = raw.lower()
    for keywords, canonical in _RULES:
        if any(kw in text for kw in keywords):
            return canonical
    return UNTHEMED


def cofog_code(coarse: Optional[str]) -> Optional[str]:
    """COFOG code for a coarse (already-canonical) theme bucket."""
    return THEME_TO_COFOG.get(coarse) if coarse else None
