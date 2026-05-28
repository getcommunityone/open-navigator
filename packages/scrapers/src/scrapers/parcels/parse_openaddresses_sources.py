#!/usr/bin/env python3
"""
Parse a cloned OpenAddresses repo and extract US Esri parcel (and optional address) layer URLs.

OpenAddresses maintains per-jurisdiction JSON under sources/us/. This script walks those
configs and emits a flat seed CSV for extract_parcel_attributes.py.

Usage:
    python packages/scrapers/src/scrapers/parcels/parse_openaddresses_sources.py --clone
    python packages/scrapers/src/scrapers/parcels/parse_openaddresses_sources.py \\
        --repo-path data/cache/openaddresses/openaddresses \\
        --layer-types parcels \\
        --validate \\
        --output data/cache/parcels/openaddresses_esri_seeds.csv
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import requests
from loguru import logger

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from esri_endpoints import (  # noqa: E402
    extract_data_url,
    is_esri_layer_url,
    validate_esri_layer,
)

DEFAULT_REPO_PATH = Path("data/cache/openaddresses/openaddresses")
DEFAULT_OUTPUT = Path("data/cache/parcels/openaddresses_esri_seeds.csv")
OPENADDRESSES_GIT = "https://github.com/openaddresses/openaddresses.git"
DEFAULT_LAYER_TYPES = ("parcels",)


def ensure_openaddresses_repo(repo_path: Path, *, clone: bool) -> Path:
    sources_us = repo_path / "sources" / "us"
    if sources_us.is_dir():
        return repo_path
    if not clone:
        raise FileNotFoundError(
            f"OpenAddresses sources not found at {sources_us}. "
            "Clone with --clone or set --repo-path to an existing checkout."
        )
    repo_path.parent.mkdir(parents=True, exist_ok=True)
    if repo_path.exists() and not (repo_path / ".git").is_dir():
        raise FileExistsError(f"{repo_path} exists but is not a git repository")

    logger.info("Cloning OpenAddresses (sparse: sources/us only)...")
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            OPENADDRESSES_GIT,
            str(repo_path),
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_path), "sparse-checkout", "set", "sources/us"],
        check=True,
    )
    if not sources_us.is_dir():
        raise RuntimeError(f"Sparse checkout failed; missing {sources_us}")
    return repo_path


def iter_config_files(sources_us: Path) -> Iterator[Path]:
    yield from sorted(sources_us.rglob("*.json"))


def relative_source_id(config_path: Path, sources_us: Path) -> str:
    rel = config_path.relative_to(sources_us)
    return str(Path("us") / rel).replace("\\", "/")


def parse_config_file(
    config_path: Path,
    *,
    sources_us: Path,
    layer_types: tuple[str, ...],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Skipping {}: {}", config_path, exc)
        return records

    if not isinstance(data, dict):
        return records

    coverage = data.get("coverage") if isinstance(data.get("coverage"), dict) else {}
    state = coverage.get("state")
    county = coverage.get("county")
    city = coverage.get("city")
    country = coverage.get("country")
    source_id = relative_source_id(config_path, sources_us)

    layers = data.get("layers")
    if not isinstance(layers, dict):
        return records

    for layer_type in layer_types:
        entries = layers.get(layer_type)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            url = extract_data_url(entry)
            if not url or not is_esri_layer_url(url):
                continue
            protocol = str(entry.get("protocol") or "").upper()
            records.append(
                {
                    "country": country,
                    "state": state,
                    "county": county,
                    "city": city,
                    "layer_type": layer_type,
                    "layer_name": entry.get("name"),
                    "protocol": protocol or None,
                    "esri_endpoint": url,
                    "source_config": config_path.name,
                    "source_id": source_id,
                    "schema": data.get("schema"),
                }
            )
    return records


def parse_openaddresses_sources(
    repo_path: Path,
    *,
    layer_types: tuple[str, ...] = DEFAULT_LAYER_TYPES,
    require_state: bool = True,
) -> pd.DataFrame:
    sources_us = repo_path / "sources" / "us"
    if not sources_us.is_dir():
        raise FileNotFoundError(f"Missing {sources_us}")

    records: list[dict[str, Any]] = []
    for config_path in iter_config_files(sources_us):
        records.extend(
            parse_config_file(config_path, sources_us=sources_us, layer_types=layer_types)
        )

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    if require_state:
        df = df[df["state"].notna() & (df["state"].astype(str).str.len() > 0)]
    df = df.drop_duplicates(subset=["esri_endpoint", "layer_type"], keep="first")
    return df.reset_index(drop=True)


VALIDATION_RESULT_COLUMNS = frozenset(
    {"ok", "queryable", "http_status", "error", "capabilities", "name", "fields_count", "layer_url"}
)


def validate_seed_frame(
    df: pd.DataFrame,
    *,
    url_column: str = "esri_endpoint",
    throttle_sec: float = 0.25,
    timeout: int = 20,
) -> pd.DataFrame:
    session = requests.Session()
    checks: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        url = row[url_column]
        result = validate_esri_layer(str(url), timeout=timeout, session=session)
        checks.append(result)
        if (idx + 1) % 50 == 0:
            logger.info("Validated {}/{} endpoints...", idx + 1, len(df))
        if throttle_sec > 0:
            time.sleep(throttle_sec)
    check_df = pd.DataFrame(checks)
    # Re-validation: drop stale probe columns so concat does not duplicate labels.
    base = df.drop(columns=[c for c in df.columns if c in VALIDATION_RESULT_COLUMNS], errors="ignore")
    return pd.concat([base.reset_index(drop=True), check_df], axis=1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Esri URLs from OpenAddresses source configs.")
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=DEFAULT_REPO_PATH,
        help=f"OpenAddresses git checkout (default: {DEFAULT_REPO_PATH})",
    )
    parser.add_argument(
        "--clone",
        action="store_true",
        help="Sparse-clone sources/us from GitHub if repo-path is missing",
    )
    parser.add_argument(
        "--layer-types",
        default=",".join(DEFAULT_LAYER_TYPES),
        help="Comma-separated OpenAddresses layer keys (default: parcels)",
    )
    parser.add_argument(
        "--include-addresses",
        action="store_true",
        help="Also harvest layers.addresses Esri endpoints",
    )
    parser.add_argument(
        "--no-require-state",
        action="store_true",
        help="Keep rows without coverage.state (rare)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Probe each endpoint with ?f=json and append ok/queryable columns",
    )
    parser.add_argument("--validate-limit", type=int, default=None, help="Validate only first N rows")
    parser.add_argument("--throttle", type=float, default=0.25, help="Seconds between validation GETs")
    args = parser.parse_args()

    layer_types = tuple(t.strip() for t in args.layer_types.split(",") if t.strip())
    if args.include_addresses and "addresses" not in layer_types:
        layer_types = (*layer_types, "addresses")

    repo_path = ensure_openaddresses_repo(args.repo_path.resolve(), clone=args.clone)
    logger.info("Scanning OpenAddresses under {}", repo_path / "sources" / "us")

    df = parse_openaddresses_sources(
        repo_path,
        layer_types=layer_types,
        require_state=not args.no_require_state,
    )
    if df.empty:
        logger.warning("No Esri endpoints found.")
        return 1

    logger.info("Found {:,} Esri layer URLs ({} layer types)", len(df), ", ".join(layer_types))

    if args.validate:
        to_check = df.head(args.validate_limit) if args.validate_limit else df
        logger.info("Validating {:,} endpoints (throttle {}s)...", len(to_check), args.throttle)
        validated = validate_seed_frame(to_check, throttle_sec=args.throttle)
        if args.validate_limit and len(df) > len(to_check):
            rest = df.iloc[len(to_check) :].copy()
            for col in ("ok", "queryable", "http_status", "error", "capabilities", "name", "fields_count", "layer_url"):
                rest[col] = None
            df = pd.concat([validated, rest], ignore_index=True)
        else:
            df = validated
        live = int(df["ok"].fillna(False).sum()) if "ok" in df.columns else 0
        logger.info("Queryable layers: {:,} / {:,}", live, len(to_check))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    logger.success("Wrote {:,} rows to {}", len(df), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
