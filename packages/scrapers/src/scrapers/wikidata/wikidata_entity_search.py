"""
Wikidata wbsearchentities + wbgetentities reconciliation helpers (avoid heavy WDQS mapping).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from scrapers.wikidata.geography_qid_cache import norm_lit


def county_search_strings(display_name: str, state_name: str) -> List[str]:
    """Build a short list of search phrases for wbsearchentities (census-style county label)."""
    n = (display_name or "").strip()
    out: List[str] = []
    if not n:
        return out
    out.append(n)
    out.append(f"{n}, {state_name}")
    out.append(f"{n} {state_name}")
    base = re.sub(
        r"\s+(County|Borough|Census Area|Municipality|Parish)\s*$",
        "",
        n,
        flags=re.IGNORECASE,
    ).strip()
    if base and base.lower() != n.lower():
        out.append(f"{base}, {state_name}")
        out.append(f"{base} {state_name}")
    # Dedupe preserving order
    seen: Set[str] = set()
    uniq: List[str] = []
    for s in out:
        k = s.strip()
        if k and k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq[:8]


def _mono_strings_from_claim(claims: Any, pid: str) -> Set[str]:
    if not claims:
        return set()
    out: Set[str] = set()
    st_list = claims.get(pid) or []
    for st in st_list:
        mainsnak = (st or {}).get("mainsnak") or {}
        dv = mainsnak.get("datavalue") or {}
        v = dv.get("value")
        if isinstance(v, str) and v.strip():
            out.add(norm_lit(v))
        elif isinstance(v, dict):
            t = v.get("text")
            if isinstance(t, str) and t.strip():
                out.add(norm_lit(t))
    return {x for x in out if x}


def entity_claim_identifier_literals(
    entity: Dict[str, Any], county_literal_targets: Set[str]
) -> Tuple[bool, Set[str]]:
    """
    Return (match, seen_literals) — match True if any P882 / P3006 / P590 normalized
    text overlaps ``county_literal_targets`` (also normalized).
    """
    claims = entity.get("claims") or {}
    targets = {norm_lit(x) for x in county_literal_targets if str(x).strip()}
    f882 = _mono_strings_from_claim(claims, "P882")
    f3006 = _mono_strings_from_claim(claims, "P3006")
    f590 = _mono_strings_from_claim(claims, "P590")
    seen = f882 | f3006 | f590
    if targets & seen:
        return True, seen
    return False, seen


def first_p131_item_id(claims: Any) -> Optional[str]:
    """First P131 mainsnak item id (Q… form), if any."""
    if not claims:
        return None
    for st in claims.get("P131") or []:
        mainsnak = (st or {}).get("mainsnak") or {}
        dv = mainsnak.get("datavalue") or {}
        val = dv.get("value")
        if isinstance(val, dict):
            if val.get("id") and str(val["id"]).startswith("Q"):
                return str(val["id"])
            num = val.get("numeric-id")
            if isinstance(num, int):
                return f"Q{num}"
    return None
