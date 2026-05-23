"""
Load OpenCivicData jurisdiction identifiers and map them to existing jurisdictions.

OpenCivicData uses canonical identifiers like:
  ocd-division/country:us/state:al/county:autauga
  ocd-division/country:us/state:ma/place:boston

This script loads the OCD data from the cached repository and creates a mapping
from our jurisdiction_id to the OCD ID.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_OCD_CACHE = Path(__file__).resolve().parents[3] / "data" / "cache" / "opencivicdata"


def _parse_ocd_id(ocd_id: str) -> dict[str, str]:
    """Parse OCD division ID into components."""
    # ocd-division/country:us/state:al/county:autauga -> {country: us, state: al, type: county, id: autauga}
    result: dict[str, str] = {}
    if not ocd_id.startswith("ocd-division/"):
        return result

    parts = ocd_id[len("ocd-division/"):].split("/")
    for part in parts:
        if ":" in part:
            key, value = part.split(":", 1)
            result[key] = value

    return result


def load_state_ocd_data(state_code: str) -> dict[str, str]:
    """
    Load OpenCivicData IDs for a state.

    Returns dict mapping canonical jurisdiction names to OCD IDs.
    Example: {"Autauga County": "ocd-division/country:us/state:al/county:autauga"}

    Priority: base jurisdictions > country-us.csv > local_gov.csv districts
    """
    state_code_lower = state_code.lower()
    ocd_data: dict[str, str] = {}
    place_to_base: dict[str, str] = {}  # Map place names to base OCD IDs

    # Priority 1: Load from state-specific local_gov.csv (has municipalities/places)
    state_csv = _OCD_CACHE / "identifiers" / "country-us" / f"state-{state_code_lower}-local_gov.csv"
    if state_csv.exists():
        try:
            with open(state_csv, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for ocd_id, name in reader:
                    if not ocd_id or not name:
                        continue

                    parsed = _parse_ocd_id(ocd_id)
                    if not parsed:
                        continue

                    # Extract base jurisdiction OCD ID (remove districts/wards/etc)
                    if "place" in parsed:
                        place_slug = parsed["place"]
                        base_ocd = f"ocd-division/country:us/state:{state_code_lower}/place:{place_slug}"
                        place_to_base[place_slug] = base_ocd
                        place_to_base[name.strip()] = base_ocd

        except Exception as exc:
            logger.debug("Failed to load local_gov data for %s: %s", state_code, exc)

    # Add the base place entries we found
    for name, base_ocd in place_to_base.items():
        if name not in ocd_data:
            ocd_data[name] = base_ocd

    # Priority 2: Load from country-us.csv (has county-level data)
    country_csv = _OCD_CACHE / "identifiers" / "country-us.csv"
    if country_csv.exists():
        try:
            with open(country_csv, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 2:
                        continue
                    ocd_id, name = row[0], row[1]
                    if not ocd_id or not name or f"state:{state_code_lower}" not in ocd_id:
                        continue

                    parsed = _parse_ocd_id(ocd_id)
                    if not parsed:
                        continue

                    # Only consider counties (not districts/school_districts)
                    if "county" not in parsed:
                        continue

                    has_subdivision = any(
                        k in parsed for k in ("council_district", "ward", "school_district", "precinct")
                    )
                    if has_subdivision:
                        continue

                    canonical_name = name.strip()
                    # Only add if not already present (places take priority)
                    if canonical_name not in ocd_data:
                        ocd_data[canonical_name] = ocd_id.strip()

                    # Also store by slug
                    county_slug = parsed.get("county")
                    if county_slug and f"{county_slug.title()} County" not in ocd_data:
                        ocd_data[f"{county_slug.title()} County"] = ocd_id.strip()

        except Exception as exc:
            logger.debug("Failed to load counties from country-us.csv: %s", exc)

    return ocd_data


def find_ocd_match(jurisdiction_name: str, state_code: str) -> str | None:
    """
    Find OCD ID for a jurisdiction by name, preferring base jurisdictions (places/counties)
    over districts/wards/school districts.

    Returns the OCD ID if found, None otherwise.
    """
    ocd_data = load_state_ocd_data(state_code)
    if not ocd_data:
        return None

    name_lower = jurisdiction_name.lower().strip()

    # First pass: look for exact matches that are base jurisdictions (no districts/wards)
    for key, ocd_id in ocd_data.items():
        if key.lower() == name_lower:
            parsed = _parse_ocd_id(ocd_id)
            # Prefer entries without districts/wards/school_districts
            has_subdivision = any(
                k in parsed for k in ("council_district", "ward", "school_district", "precinct")
            )
            if not has_subdivision:
                return ocd_id

    # Second pass: try normalized name match (remove "City of", "County", etc.)
    normalized_name = re.sub(
        r"^(?:city|town|county|village|borough|municipality|cdp)\s+(?:of\s+)?",
        "",
        name_lower,
        flags=re.IGNORECASE,
    )

    for key, ocd_id in ocd_data.items():
        if key.lower() == normalized_name:
            parsed = _parse_ocd_id(ocd_id)
            has_subdivision = any(
                k in parsed for k in ("council_district", "ward", "school_district", "precinct")
            )
            if not has_subdivision:
                return ocd_id

    # Final fallback: return any match (including districts)
    for key, ocd_id in ocd_data.items():
        if key.lower() == name_lower:
            return ocd_id

    logger.debug("No OCD match for %s %s", state_code, jurisdiction_name)
    return None


def load_ocd_jurisdictions_for_states(state_codes: list[str]) -> dict[tuple[str, str], str]:
    """
    Load all OCD jurisdiction mappings for given states.

    Returns dict mapping (state_code, jurisdiction_name) -> ocd_id
    """
    result: dict[tuple[str, str], str] = {}

    for state_code in state_codes:
        ocd_data = load_state_ocd_data(state_code)
        for name, ocd_id in ocd_data.items():
            parsed = _parse_ocd_id(ocd_id)
            # Only include counties and places (municipalities), skip districts/precincts
            if parsed.get("county") or parsed.get("place"):
                result[(state_code, name)] = ocd_id

    logger.info("Loaded %d OCD jurisdiction mappings across %d states", len(result), len(state_codes))
    return result
