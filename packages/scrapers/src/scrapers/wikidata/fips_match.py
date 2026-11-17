"""
Census identifier literals for matching bronze jurisdictions to Wikidata items.

These helpers decide which identifier strings may link a bronze row (keyed on its
Census GEOID) to a Wikidata item. They replace the ones in the archived
``load_jurisdictions_wikidata`` monolith.

Counties match on the **full 5-digit FIPS** only (Wikidata ``P882``): state FIPS
(2 digits) + county FIPS (3 digits). The old helper also emitted the bare 3- and
4-digit tails ("003", "8003"). Those are not unique across states, so a global
lookup keyed on them returned whichever state was loaded first: Allen County,
Indiana (18003) received Baldwin County, Alabama's item (Q156163, FIPS 01003),
and Puerto Rico (72) items leaked into other states the same way (issue #461).

Municipalities match on the 7-digit place GEOID (state + place FIPS, ``P774``)
and the GNIS id (``P590``), both of which already carry or imply the state.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional, Set, Tuple


def norm_lit(x: object) -> str:
    """Strip whitespace and hyphens (``"18-003"`` → ``"18003"``)."""
    return re.sub(r"[\s\-]+", "", str(x).strip())


def normalize_county_geoid(geoid: object) -> Optional[str]:
    """Return the 5-digit county GEOID, or ``None`` when it is not one.

    A 4-digit value is a 5-digit code that lost its leading zero (``"1003"`` →
    ``"01003"``); anything shorter is a county-only code without its state and
    cannot identify a county on its own.
    """
    if geoid is None:
        return None
    g = norm_lit(geoid)
    if not g.isdigit():
        return None
    if len(g) == 4:
        g = g.zfill(5)
    return g if len(g) == 5 else None


def county_fips_literals(geoid: object, state_fips: Optional[str] = None) -> Set[str]:
    """Identifier literals that may match a county's Wikidata ``P882``.

    Only the full 5-digit FIPS is returned. When ``state_fips`` is given and the
    GEOID does not start with it, nothing is returned: the row and its state
    disagree, so no item can be trusted for it.
    """
    g = normalize_county_geoid(geoid)
    if not g:
        return set()
    sf = norm_lit(state_fips or "")
    if sf:
        if not sf.isdigit():
            return set()
        if not g.startswith(sf.zfill(2)):
            return set()
    return {g}


def county_p882_to_geoid(p882: object, state_fips: Optional[str] = None) -> Optional[str]:
    """Normalize a county item's ``P882`` value to a 5-digit GEOID.

    Wikidata sometimes stores only the 3-digit county code. That form is accepted
    only when the caller knows the item's state (``state_fips``), for example from
    a query scoped to one state or from the item's ``P131`` state. Without a
    state, a short code is rejected rather than guessed.
    """
    if p882 is None:
        return None
    v = norm_lit(p882)
    if not v.isdigit():
        return None
    sf = norm_lit(state_fips or "")
    sf = sf.zfill(2) if sf.isdigit() else ""
    if len(v) == 5:
        geoid = v
    elif len(v) == 4:
        geoid = v.zfill(5)
    elif len(v) <= 3 and sf:
        geoid = f"{sf}{v.zfill(3)}"
    else:
        return None
    if sf and not geoid.startswith(sf):
        return None
    return geoid


def county_item_matches(
    geoid: object,
    item_p882_values: Iterable[object],
    item_state_fips: Optional[str] = None,
) -> bool:
    """True when one of the item's ``P882`` values is exactly the county's GEOID.

    ``item_state_fips`` (the state FIPS of the item's ``P131`` state) is used to
    widen a bare 3-digit ``P882`` and must agree with the GEOID's state prefix.
    """
    g = normalize_county_geoid(geoid)
    if not g:
        return False
    if item_state_fips:
        sf = norm_lit(item_state_fips)
        if not (sf.isdigit() and g.startswith(sf.zfill(2))):
            return False
    for raw in item_p882_values:
        if county_p882_to_geoid(raw, item_state_fips) == g:
            return True
    return False


def municipality_wd_literal_sets(geoid: object, ansicode: Optional[object]) -> Tuple[Set[str], Set[str]]:
    """Place literals for ``P774`` (7-digit state+place FIPS) and ``P590`` (GNIS).

    Every FIPS literal keeps the 2-digit state prefix, so a place in one state
    cannot match another state's place with the same 5-digit place code.
    """
    fips_lit: Set[str] = set()
    gnis_lit: Set[str] = set()
    raw_geo = str(geoid).strip() if geoid is not None else ""
    if not raw_geo:
        return fips_lit, gnis_lit
    d = norm_lit(raw_geo)
    if d.isdigit():
        if len(d) == 7:
            fips_lit.add(d)
        elif len(d) == 6:
            # 7-digit place GEOID that lost its leading zero.
            fips_lit.add(d.zfill(7))
        elif len(d) > 7:
            fips_lit.add(d[:7])
        # Shorter values carry no state prefix: no FIPS literal.
    elif d:
        fips_lit.add(d)
    if ansicode is not None and str(ansicode).strip():
        raw = norm_lit(ansicode)
        gnis_lit.add(raw)
        if raw.isdigit():
            gnis_lit.add(raw.lstrip("0") or "0")
    return fips_lit, gnis_lit


def school_id_literal_alternatives(geoid_or_nces: object) -> Set[str]:
    """NCES district id forms (7-digit, state prefix included)."""
    s = norm_lit(geoid_or_nces or "")
    if not s:
        return set()
    out: Set[str] = {s}
    if s.isdigit():
        t = s.lstrip("0") or "0"
        out.update({t, s.zfill(7), t.zfill(7)})
    return {x for x in out if x}
