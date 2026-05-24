#!/usr/bin/env python3
"""
Fold ``public.organization_location`` (571,448 rows of HIFLD-style location data:
places of worship, police stations, hospitals, sheriffs, state agencies, etc.)
into ``public.c1_organization`` and then drop the source table.

Mapping:

  organization_location           ->  c1_organization
  ─────────────────────────────       ──────────────────────────────────────
  source_id                            extras['source_id']
  name                                 name
  organization_type                    classification          (normalized: slashes → underscores)
  address                              address
  city                                 city
  state                                state
  state_name                           extras['state_name']
  zip                                  zip_code
  county                               county
  latitude                             latitude                (NEW column from 054a)
  longitude                            longitude               (NEW column from 054a)
  telephone                            phone
  website                              website
  data_source                          source
  source_dataset                       extras['source_dataset']
  additional_info                      extras (merged)
  created_at                           created_at
  updated_at                           updated_at

Jurisdiction binding: each row's (state, city) is looked up in the cached OCD
``country-us.csv`` (places + counties). Matches produce the canonical OCD
jurisdiction URN, e.g. ``ocd-jurisdiction/country:us/state:ms/place:natchez/government``.
Unmatched rows get NULL jurisdiction_id.

Deterministic ``id``: ocd-organization/<UUIDv5 from data_source+source_id+name+city+state>
so re-runs upsert cleanly.

Run::

    .venv/bin/python -m scripts.discovery.fold_organization_location_into_c1 --dry-run
    .venv/bin/python -m scripts.discovery.fold_organization_location_into_c1
    .venv/bin/python -m scripts.discovery.fold_organization_location_into_c1 --drop-source

``--drop-source`` runs migration 054b after the fold (drops public.organization_location).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import uuid
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

logger = logging.getLogger("fold_organization_location")

_OCD_NS_ORG = uuid.UUID("a8b3c4d5-e6f7-4a89-9b1c-2d3e4f5a6b7c")
_OCD_CSV = _ROOT / "data" / "cache" / "opencivicdata" / "identifiers" / "country-us.csv"


# --------------------------------------------------------------------------------------
# Jurisdiction-id lookup from OCD country-us.csv
# --------------------------------------------------------------------------------------


def _normalize_place_name(name: str) -> str:
    """Strip LSAD suffix + lowercase + collapse whitespace + drop punctuation."""
    s = (name or "").strip().lower()
    s = re.sub(r"\s+(city|town|village|borough|cdp|municipality|township)$", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def build_ocd_lookup() -> dict[tuple[str, str], str]:
    """
    Return ``{(state_code_lower, normalized_place): ocd_jurisdiction_id}`` covering all
    US places + counties. The OCD ``ocd-division`` URN gets transformed to
    ``ocd-jurisdiction`` with ``/government`` suffix per the canonical jurisdiction form.
    """
    if not _OCD_CSV.exists():
        raise SystemExit(f"OCD CSV not found at {_OCD_CSV} — run wikidata cache warm first")
    lookup: dict[tuple[str, str], str] = {}
    with open(_OCD_CSV) as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            ocd_id, name = row[0], row[1]
            # Places
            m = re.match(r"^ocd-division/country:us/state:([a-z]{2})/place:([a-z0-9_]+)$", ocd_id)
            if m:
                state, slug = m.group(1), m.group(2)
                juris = f"ocd-jurisdiction/country:us/state:{state}/place:{slug}/government"
                lookup[(state, slug)] = juris
                # Also map the display-name normalized form
                lookup[(state, _normalize_place_name(name))] = juris
                continue
            # Counties
            m = re.match(r"^ocd-division/country:us/state:([a-z]{2})/county:([a-z0-9_]+)$", ocd_id)
            if m:
                state, slug = m.group(1), m.group(2)
                juris = f"ocd-jurisdiction/country:us/state:{state}/county:{slug}/government"
                # County lookups keyed under county slug; org rows have city not county usually,
                # but if city is empty and county matches, we use this.
                lookup[(state, f"_county:{slug}")] = juris
                lookup[(state, _normalize_place_name(name))] = juris
    return lookup


def derive_jurisdiction_id(
    state: str | None, city: str | None, county: str | None,
    lookup: dict[tuple[str, str], str],
) -> str | None:
    if not state:
        return None
    state_lc = state.strip().lower()[:2]
    if not state_lc:
        return None
    # Prefer city (place); fall back to county.
    if city:
        ocd = lookup.get((state_lc, _normalize_place_name(city)))
        if ocd:
            return ocd
    if county:
        ocd = lookup.get((state_lc, _normalize_place_name(county)))
        if ocd:
            return ocd
        # county-prefixed lookup
        ocd = lookup.get((state_lc, f"_county:{_normalize_place_name(county)}"))
        if ocd:
            return ocd
    return None


# --------------------------------------------------------------------------------------
# Row mapping
# --------------------------------------------------------------------------------------


def _normalize_classification(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or None


def _det_org_id(data_source: str | None, source_id: str | None, name: str | None,
                city: str | None, state: str | None) -> str:
    """UUIDv5 over the most-stable identity fields so re-fold upserts cleanly."""
    seed = "|".join((data_source or "", source_id or "", name or "", city or "", state or ""))
    u = uuid.uuid5(_OCD_NS_ORG, seed)
    return f"ocd-organization/{u}"


# --------------------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------------------


def fold(*, dry_run: bool, drop_source: bool) -> None:
    src_db = os.getenv("NEON_DATABASE_URL_DEV", "").strip()
    if not src_db:
        raise SystemExit("NEON_DATABASE_URL_DEV not set")

    logger.info("Building OCD jurisdiction-id lookup from %s …", _OCD_CSV.name)
    lookup = build_ocd_lookup()
    logger.info("Lookup size: %d (state, normalized-name) keys", len(lookup))

    conn = psycopg2.connect(src_db)
    try:
        with conn.cursor(name="org_loc_stream") as src:
            src.itersize = 5000
            src.execute("""
                SELECT id, source_id, name, organization_type, address, city, state,
                       state_name, zip, county, latitude, longitude, telephone,
                       website, data_source, source_dataset, additional_info,
                       created_at, updated_at
                FROM public.organization_location
            """)

            batch: list[tuple] = []
            n_streamed = 0
            n_inserted = 0
            n_jur_matched = 0
            type_dist: dict[str, int] = {}

            with conn.cursor() as dst:
                while True:
                    rows = src.fetchmany(5000)
                    if not rows:
                        break
                    for r in rows:
                        (_loc_id, source_id, name, org_type, address, city, state,
                         state_name, zip_code, county, lat, lon, phone, website,
                         data_source, source_dataset, addl_info,
                         created_at, updated_at) = r

                        classification = _normalize_classification(org_type)
                        if classification:
                            type_dist[classification] = type_dist.get(classification, 0) + 1

                        jurisdiction_id = derive_jurisdiction_id(state, city, county, lookup)
                        if jurisdiction_id:
                            n_jur_matched += 1

                        org_id = _det_org_id(data_source, source_id, name, city, state)

                        extras = {}
                        if isinstance(addl_info, dict):
                            extras.update(addl_info)
                        if source_id:        extras["source_id"] = source_id
                        if state_name:       extras["state_name"] = state_name
                        if source_dataset:   extras["source_dataset"] = source_dataset

                        batch.append((
                            org_id, name, classification, jurisdiction_id,
                            address, city, state, county, zip_code,
                            lat, lon, phone, website,
                            (data_source or "organization_location"),
                            psycopg2.extras.Json(extras),
                            created_at, updated_at,
                        ))
                        n_streamed += 1

                    if not dry_run and batch:
                        execute_values(
                            dst,
                            """
                            INSERT INTO public.c1_organization
                              (id, name, classification, jurisdiction_id,
                               address, city, state, county, zip_code,
                               latitude, longitude, phone, website,
                               source, extras, created_at, updated_at)
                            VALUES %s
                            ON CONFLICT (ein) WHERE ein IS NOT NULL DO NOTHING
                            """,
                            batch,
                        )
                        n_inserted += len(batch)
                        if n_streamed % 50000 == 0 or n_streamed == len(rows):
                            logger.info("  streamed %d / inserted %d / jur_matched %d",
                                        n_streamed, n_inserted, n_jur_matched)
                    batch.clear()

            if not dry_run:
                conn.commit()

    finally:
        conn.close()

    print()
    print(f"Rows streamed:          {n_streamed:,}")
    print(f"Rows inserted:          {n_inserted:,}{'  (dry-run: 0)' if dry_run else ''}")
    print(f"Jurisdiction-id matched:{n_jur_matched:,}  ({100*n_jur_matched/max(1,n_streamed):.1f}%)")
    print(f"Classification dist:")
    for cls, n in sorted(type_dist.items(), key=lambda kv: -kv[1]):
        print(f"  {cls:30s} {n:,}")

    if drop_source and not dry_run:
        logger.info("Dropping public.organization_location …")
        conn = psycopg2.connect(src_db)
        try:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE public.organization_location CASCADE")
            conn.commit()
            print("\npublic.organization_location dropped.")
        finally:
            conn.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--drop-source", action="store_true",
                   help="Drop public.organization_location after successful fold")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    fold(dry_run=args.dry_run, drop_source=args.drop_source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
