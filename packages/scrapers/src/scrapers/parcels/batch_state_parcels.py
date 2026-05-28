#!/usr/bin/env python3
"""
Extract and load parcel attributes for all counties in a state (OpenAddresses + manual overrides).

Usage:
    .venv/bin/python packages/scrapers/src/scrapers/parcels/batch_state_parcels.py --state AL
    .venv/bin/python packages/scrapers/src/scrapers/parcels/batch_state_parcels.py --state AL --skip-extract
    .venv/bin/python packages/scrapers/src/scrapers/parcels/batch_state_parcels.py --state AL --counties Jefferson,Shelby
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from esri_endpoints import validate_esri_layer  # noqa: E402
from extract_parcel_attributes import extract_parcel_attributes  # noqa: E402
# The inline CSV->bronze loader was ported out of this scraper into the LAND
# pipeline `ingestion.arcgis.addresses` (reads data/cache/parcels). This batch
# tool now covers FETCH/extract only; run it with --skip-load and land via
# `python -m ingestion.arcgis.addresses`.

from scripts.database.target_database_url import resolve_target_database_url  # noqa: E402

OA_ROOT = _PROJECT_ROOT / "data/cache/openaddresses/openaddresses/sources/us"
CACHE_STATE = _PROJECT_ROOT / "data/cache/parcels"
CENSUS_COUNTIES = _PROJECT_ROOT / "data/cache/census/gazetteer/counties.csv"
OVERRIDES_PATH = _SCRIPT_DIR / "seeds/al_manual_overrides.json"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower().strip())
    return s.strip("_")


def _dataset_key(state: str, county: str) -> str:
    return f"{state.lower()}_{_slug(county)}_county_parcels"


def _load_census_fips(state: str) -> pd.DataFrame:
    df = pd.read_csv(CENSUS_COUNTIES, dtype=str)
    df = df[df["USPS"].str.upper() == state.upper()].copy()
    df["county_name"] = df["NAME"].str.replace(" County", "", regex=False)
    return df


def discover_state_jobs(state: str) -> list[dict[str, Any]]:
    state_lower = state.lower()
    oa_dir = OA_ROOT / state_lower
    jobs: list[dict[str, Any]] = []
    seen_counties: set[str] = set()

    if oa_dir.is_dir():
        for path in sorted(oa_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            cov = data.get("coverage") if isinstance(data.get("coverage"), dict) else {}
            county = (cov.get("county") or path.stem.replace("_", " ")).strip()
            if not county or county.lower() in seen_counties:
                continue
            parcels = (data.get("layers") or {}).get("parcels")
            if not isinstance(parcels, list) or not parcels:
                continue
            url = parcels[0].get("data") if isinstance(parcels[0], dict) else None
            if not url:
                continue
            geoid = (cov.get("US Census") or {}).get("geoid")
            seen_counties.add(county.lower())
            jobs.append(
                {
                    "county": county,
                    "geoid": geoid,
                    "esri_endpoint": str(url).strip(),
                    "source_id": f"us/{state_lower}/{path.name}",
                }
            )

    overrides_file = _SCRIPT_DIR / "seeds" / f"{state_lower}_manual_overrides.json"
    if overrides_file.is_file():
        for entry in json.loads(overrides_file.read_text(encoding="utf-8")):
            county = entry["county"]
            if county.lower() in seen_counties:
                continue
            seen_counties.add(county.lower())
            jobs.append(
                {
                    "county": county,
                    "geoid": entry.get("geoid"),
                    "esri_endpoint": entry["esri_endpoint"],
                    "source_id": f"manual/{_slug(county)}",
                }
            )

    census = _load_census_fips(state)
    name_to_geoid = {r["county_name"].lower(): r["GEOID"] for _, r in census.iterrows()}
    for job in jobs:
        if not job.get("geoid") and job["county"]:
            job["geoid"] = name_to_geoid.get(job["county"].lower())

    jobs.sort(key=lambda j: j["county"].lower())
    return jobs


def run_batch(
    state: str,
    *,
    jobs: list[dict[str, Any]],
    force_extract: bool,
    skip_extract: bool,
    skip_load: bool,
    validate: bool,
    db_url: str,
) -> dict[str, Any]:
    state_upper = state.upper()
    out_dir = CACHE_STATE / state.lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "_batch_manifest.json"

    results: list[dict[str, Any]] = []
    for i, job in enumerate(jobs, 1):
        county = job["county"]
        slug = _slug(county)
        csv_path = out_dir / f"{slug}_county_attrs.csv"
        dataset = _dataset_key(state, county)
        geoid = job.get("geoid")
        endpoint = job["esri_endpoint"]
        rec: dict[str, Any] = {
            "county": county,
            "geoid": geoid,
            "dataset": dataset,
            "esri_endpoint": endpoint,
            "csv_path": str(csv_path.relative_to(_PROJECT_ROOT)),
            "status": "pending",
        }
        logger.info("=== [{}/{}] {} County, {} ===", i, len(jobs), county, state_upper)

        try:
            if validate:
                probe = validate_esri_layer(endpoint)
                rec["validation"] = probe
                if not probe.get("ok"):
                    rec["status"] = "skipped_not_queryable"
                    rec["error"] = probe.get("error")
                    results.append(rec)
                    continue

            if not skip_extract:
                if force_extract or not csv_path.is_file():
                    extract_parcel_attributes(
                        endpoint,
                        output_csv=csv_path,
                        normalize_fields=True,
                    )
                    if not csv_path.is_file() or csv_path.stat().st_size < 50:
                        rec["status"] = "extract_empty"
                        results.append(rec)
                        continue
                else:
                    logger.info("Using cached CSV {}", csv_path)
                rec["csv_rows"] = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1

            if not skip_load and csv_path.is_file():
                raise NotImplementedError(
                    "Inline bronze loading was removed from this scraper when the "
                    "loader was ported to ingestion.arcgis.addresses. Re-run with "
                    "skip_load=True (FETCH/extract only), then LAND the extracted "
                    "CSVs in data/cache/parcels/ via: python -m ingestion.arcgis.addresses"
                )
            elif skip_load:
                rec["status"] = "extract_only"

        except Exception as exc:
            logger.exception("{} failed: {}", county, exc)
            rec["status"] = "error"
            rec["error"] = str(exc)

        results.append(rec)
        time.sleep(0.5)

    summary = {
        "state": state_upper,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total_jobs": len(jobs),
        "ok": sum(1 for r in results if r.get("status") == "ok"),
        "failed": sum(1 for r in results if r.get("status") == "error"),
        "skipped": sum(1 for r in results if r.get("status", "").startswith("skipped")),
        "results": results,
    }
    manifest_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.success("Manifest: {}", manifest_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch extract/load state county parcel layers.")
    parser.add_argument("--state", default="AL", help="USPS state code (default: AL)")
    parser.add_argument("--counties", help="Comma-separated county names to run (default: all discovered)")
    parser.add_argument("--force-extract", action="store_true", help="Re-download even if CSV exists")
    parser.add_argument("--skip-extract", action="store_true", help="Only load existing CSVs")
    parser.add_argument("--skip-load", action="store_true", help="Only extract to CSV")
    parser.add_argument("--no-validate", action="store_true", help="Skip pre-flight ?f=json check")
    parser.add_argument("--list-only", action="store_true", help="Print discovered jobs and exit")
    args = parser.parse_args()

    jobs = discover_state_jobs(args.state)
    if args.counties:
        want = {c.strip().lower() for c in args.counties.split(",") if c.strip()}
        jobs = [j for j in jobs if j["county"].lower() in want]

    census = _load_census_fips(args.state)
    covered = {j["county"].lower() for j in jobs}
    missing = census[~census["county_name"].str.lower().isin(covered)]

    logger.info(
        "Discovered {} parcel endpoints for {} ({} counties in Census, {} without endpoint)",
        len(jobs),
        args.state.upper(),
        len(census),
        len(missing),
    )
    if len(missing):
        logger.warning(
            "No public OA/manual endpoint for: {}",
            ", ".join(missing["county_name"].tolist()),
        )

    if args.list_only:
        for j in jobs:
            print(f"{j['county']:20} {j.get('geoid','?'):6} {j['esri_endpoint']}")
        return 0

    if not jobs:
        logger.error("No jobs to run.")
        return 1

    summary = run_batch(
        args.state,
        jobs=jobs,
        force_extract=args.force_extract,
        skip_extract=args.skip_extract,
        skip_load=args.skip_load,
        validate=not args.no_validate,
        db_url=resolve_target_database_url(),
    )
    logger.info(
        "Done: {} ok, {} failed, {} skipped / {}",
        summary["ok"],
        summary["failed"],
        summary["skipped"],
        summary["total_jobs"],
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
