#!/usr/bin/env python3
"""
Geocode ``places[]`` in Part 1 analysis JSON and validate cross-refs to decisions.

Uses OpenStreetMap Nominatim (same pattern as frontend AddressLookup). Respect
https://operations.osmfoundation.org/policies/nominatim/ — 1 req/s, identifiable UA.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = "OpenNavigator-PolicyAnalysis/1.0 (civic-meeting-research)"

# Known scrape targets → geocode bias
JURISDICTION_GEO_HINTS: Dict[str, Dict[str, str]] = {
    "municipality_0177256": {
        "city": "Tuscaloosa",
        "state": "AL",
        "country": "us",
    },
}


def _slug_place_id(raw: str, jurisdiction_id: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (raw or "unknown").lower()).strip("_")[:60]
    return f"place_{base}_{jurisdiction_id}" if base else f"place_unknown_{jurisdiction_id}"


def _nominatim_geocode(
    query: str,
    *,
    city: str = "",
    state: str = "",
    country: str = "us",
) -> Optional[Dict[str, Any]]:
    q = query.strip()
    if city and city.lower() not in q.lower():
        q = f"{q}, {city}"
    if state and state.upper() not in q.upper():
        q = f"{q}, {state}"
    params = {
        "q": q,
        "format": "json",
        "addressdetails": "1",
        "countrycodes": country,
        "limit": "1",
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Nominatim failed for {!r}: {}", query, exc)
        return None
    if not data:
        return None
    hit = data[0]
    addr = hit.get("address") or {}
    return {
        "latitude": float(hit["lat"]),
        "longitude": float(hit["lon"]),
        "display_name": hit.get("display_name"),
        "osm_type": hit.get("osm_type"),
        "osm_id": hit.get("osm_id"),
        "street": addr.get("road") or addr.get("pedestrian"),
        "house_number": addr.get("house_number"),
        "city": (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("municipality")
        ),
        "state": addr.get("state"),
        "postal_code": addr.get("postcode"),
        "county": addr.get("county"),
    }


def _needs_geocode(place: Dict[str, Any]) -> bool:
    if place.get("geocode_status") == "ok" and place.get("latitude") is not None:
        return False
    return bool((place.get("geocode_query") or place.get("normalized_address") or "").strip())


_STREET_ADDRESS_RE = re.compile(
    r"\b(\d{1,5}\s+(?:[A-Za-z0-9'.&]+\s+)+"
    r"(?:Avenue|Ave|Street|St|Drive|Dr|Road|Rd|Place|Pl|Boulevard|Blvd|Circle|Cir|"
    r"Way|Lane|Ln|Court|Ct|Hillcrest))\b",
    re.IGNORECASE,
)
_SUBJECT_SITE_SUFFIX_RE = re.compile(
    r"\s+(?:Rear\s+Patio|Tree\s+Removal|Addition|Fence|Handrails|"
    r"Exterior\s+Alterations|Sign\s+Replacement|Duplex\s+Construction|"
    r"Continuation)\s*$",
    re.IGNORECASE,
)


def _extract_street_address(text: str) -> str:
    """Best-effort Tuscaloosa-style street line from subject label or description."""
    text = (text or "").strip()
    if not text:
        return ""
    match = _STREET_ADDRESS_RE.search(text)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    if " - " in text:
        tail = text.split(" - ", 1)[-1].strip()
        tail = _SUBJECT_SITE_SUFFIX_RE.sub("", tail).strip()
        match = _STREET_ADDRESS_RE.search(tail)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
        if re.match(r"^\d", tail):
            return tail[:80].strip()
    return ""


def infer_places_from_analysis(
    analysis: Dict[str, Any],
    *,
    jurisdiction_id: str = "",
) -> Dict[str, Any]:
    """
    Build ``places[]`` and ``place_refs`` from ``subjects[]`` / decision text when Part 1 omitted them.
    """
    out = json.loads(json.dumps(analysis, ensure_ascii=False))
    jid = (
        jurisdiction_id
        or (out.get("meeting") or {}).get("jurisdiction")
        or ""
    ).strip()
    hint = JURISDICTION_GEO_HINTS.get(jid, {})
    city = hint.get("city", "Tuscaloosa")
    state = hint.get("state", "AL")

    subjects_by_id: Dict[str, Dict[str, Any]] = {
        s["subject_id"]: s
        for s in (out.get("subjects") or [])
        if isinstance(s, dict) and s.get("subject_id")
    }
    places: List[Dict[str, Any]] = [
        p for p in (out.get("places") or []) if isinstance(p, dict)
    ]
    by_address: Dict[str, Dict[str, Any]] = {}
    for place in places:
        key = (place.get("normalized_address") or place.get("raw_text") or "").strip().lower()
        if key:
            by_address[key] = place

    def _ensure_place(address: str, *, raw_text: str = "", subject: Optional[Dict[str, Any]] = None) -> str:
        address = re.sub(r"\s+", " ", (address or "").strip())
        if not address:
            return ""
        norm = f"{address}, {city}, {state}" if city else address
        key = norm.lower()
        if key not in by_address:
            pid = _slug_place_id(address, jid or "unknown")
            row: Dict[str, Any] = {
                "place_id": pid,
                "raw_text": raw_text or (subject or {}).get("subject_description") or address,
                "label": address,
                "normalized_address": norm,
                "place_type": "street_address",
                "street_address": address,
                "city": city,
                "state": state,
                "geocode_query": norm,
                "geocode_status": "pending",
                "linked_decision_ids": [],
                "linked_item_ids": [],
            }
            by_address[key] = row
            places.append(row)
        return by_address[key]["place_id"]

    for subject in subjects_by_id.values():
        addr = _extract_street_address(subject.get("subject_label") or "")
        if not addr:
            addr = _extract_street_address(subject.get("subject_description") or "")
        if not addr:
            continue
        pid = _ensure_place(addr, subject=subject)
        subject["primary_place_id"] = pid

    for decision in out.get("decisions") or []:
        if not isinstance(decision, dict):
            continue
        did = str(decision.get("decision_id") or "")
        subject = subjects_by_id.get(str(decision.get("subject_id") or ""))
        addr = ""
        if subject:
            addr = _extract_street_address(subject.get("subject_label") or "")
            if not addr:
                addr = _extract_street_address(subject.get("subject_description") or "")
        if not addr:
            addr = _extract_street_address(decision.get("decision_statement") or "")
            addr = addr or _extract_street_address(decision.get("headline") or "")
        if not addr:
            continue
        pid = _ensure_place(
            addr,
            raw_text=decision.get("decision_statement") or "",
            subject=subject,
        )
        decision["primary_place_id"] = pid
        refs = list(decision.get("place_refs") or [])
        if pid not in refs:
            refs.insert(0, pid)
        decision["place_refs"] = refs
        for place in by_address.values():
            if place.get("place_id") == pid and did:
                ids = place.setdefault("linked_decision_ids", [])
                if did not in ids:
                    ids.append(did)

    out["places"] = places
    return link_places_cross_refs(out)


def link_places_cross_refs(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure place_refs on decisions/uncontested point at existing places[]."""
    out = analysis
    known = {
        p["place_id"]
        for p in (out.get("places") or [])
        if isinstance(p, dict) and p.get("place_id")
    }
    for key in ("decisions", "uncontested_items"):
        for row in out.get(key) or []:
            if not isinstance(row, dict):
                continue
            refs = row.get("place_refs")
            if not isinstance(refs, list):
                refs = []
            refs = [r for r in refs if r in known]
            if row.get("primary_place_id") and row["primary_place_id"] in known:
                if row["primary_place_id"] not in refs:
                    refs.insert(0, row["primary_place_id"])
            row["place_refs"] = refs
    return out


def enrich_places_in_analysis(
    analysis: Dict[str, Any],
    *,
    jurisdiction_id: str = "",
    geocode: bool = True,
    nominatim_delay_s: float = 1.1,
) -> Dict[str, Any]:
    """
    Validate ``places[]`` cross-refs; optionally fill lat/lon via Nominatim.
    """
    out = json.loads(json.dumps(analysis, ensure_ascii=False))
    jid = (
        jurisdiction_id
        or (out.get("meeting") or {}).get("jurisdiction")
        or ""
    ).strip()
    hint = JURISDICTION_GEO_HINTS.get(jid, {})
    city = hint.get("city", "")
    state = hint.get("state", "")
    country = hint.get("country", "us")

    if not (out.get("places") or []):
        out = infer_places_from_analysis(out, jurisdiction_id=jid)

    places = out.get("places")
    if not isinstance(places, list):
        places = []
        out["places"] = places

    for place in places:
        if not isinstance(place, dict):
            continue
        raw = (
            place.get("normalized_address")
            or place.get("raw_text")
            or place.get("label")
            or ""
        )
        if not place.get("place_id") and raw:
            place["place_id"] = _slug_place_id(raw, jid or "unknown")
        place.setdefault("jurisdiction_id", jid)
        place.setdefault("geocode_query", raw)
        if not geocode or not _needs_geocode(place):
            continue
        query = (place.get("geocode_query") or raw).strip()
        if not query:
            place["geocode_status"] = "skipped"
            continue
        geo = _nominatim_geocode(query, city=city, state=state, country=country)
        time.sleep(nominatim_delay_s)
        if geo:
            place.update(geo)
            place["geocode_status"] = "ok"
            place["geocode_source"] = "nominatim"
        else:
            place["geocode_status"] = "not_found"

    return link_places_cross_refs(out)


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis_json", type=Path)
    parser.add_argument("--jurisdiction-id", default="")
    parser.add_argument("--geocode", action="store_true")
    parser.add_argument(
        "--infer-missing",
        action="store_true",
        help="Build places[] from subjects/decisions when Part 1 omitted them (default when places empty)",
    )
    parser.add_argument("--in-place", action="store_true", default=True)
    args = parser.parse_args()
    data = json.loads(args.analysis_json.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Expected JSON object")
    jid = args.jurisdiction_id or (data.get("meeting") or {}).get("jurisdiction") or ""
    if args.infer_missing or not (data.get("places") or []):
        data = infer_places_from_analysis(data, jurisdiction_id=jid)
    enriched = enrich_places_in_analysis(
        data, jurisdiction_id=jid, geocode=args.geocode
    )
    out_path = args.analysis_json if args.in_place else args.analysis_json.with_suffix(".places.json")
    out_path.write_text(json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n = len(enriched.get("places") or [])
    ok = sum(
        1
        for p in enriched.get("places") or []
        if isinstance(p, dict) and p.get("geocode_status") == "ok"
    )
    logger.info("Wrote {} ({} places, {} geocoded)", out_path, n, ok)


if __name__ == "__main__":
    main()
