#!/usr/bin/env python3
"""
Validate a parcel seed CSV (from OpenAddresses or Hub scouts) before full attribute pulls.

Appends ok, queryable, capabilities, and error columns via ?f=json layer metadata checks.

Usage:
    python packages/scrapers/src/scrapers/parcels/validate_parcel_seeds.py \\
        --input data/cache/parcels/openaddresses_esri_seeds.csv \\
        --url-column esri_endpoint \\
        --output data/cache/parcels/openaddresses_esri_seeds_validated.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from parse_openaddresses_sources import VALIDATION_RESULT_COLUMNS, validate_seed_frame  # noqa: E402

URL_COLUMN_CANDIDATES = ("esri_endpoint", "source_endpoint", "url", "endpoint")


def detect_url_column(df: pd.DataFrame, preferred: str | None) -> str:
    if preferred:
        if preferred not in df.columns:
            raise ValueError(f"Column not found: {preferred}")
        return preferred
    for col in URL_COLUMN_CANDIDATES:
        if col in df.columns:
            return col
    raise ValueError(
        f"No URL column found. Expected one of {URL_COLUMN_CANDIDATES}; got {list(df.columns)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Esri parcel seed URLs in a CSV.")
    parser.add_argument("--input", "-i", type=Path, required=True)
    parser.add_argument("--output", "-o", type=Path, default=None, help="Default: overwrite input")
    parser.add_argument("--url-column", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--throttle", type=float, default=0.25)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument(
        "--queryable-only",
        action="store_true",
        help="Write only rows where validation ok=true",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    dup_cols = df.columns[df.columns.duplicated()].tolist()
    if dup_cols:
        logger.warning("Dropping duplicate input columns: {}", dup_cols)
        df = df.loc[:, ~df.columns.duplicated()]
    df = df.drop(columns=[c for c in df.columns if c in VALIDATION_RESULT_COLUMNS], errors="ignore")
    url_col = detect_url_column(df, args.url_column)
    to_check = df.head(args.limit) if args.limit else df

    logger.info("Validating {:,} rows ({})...", len(to_check), url_col)
    validated = validate_seed_frame(to_check, url_column=url_col, throttle_sec=args.throttle, timeout=args.timeout)

    if args.limit and len(df) > len(to_check):
        rest = df.iloc[len(to_check) :].copy()
        for col in validated.columns:
            if col not in rest.columns and col not in df.columns:
                rest[col] = None
        out = pd.concat([validated, rest], ignore_index=True)
    else:
        out = validated

    if out.columns.duplicated().any():
        dup = out.columns[out.columns.duplicated()].tolist()
        logger.warning("Dropping duplicate output columns: {}", dup)
        out = out.loc[:, ~out.columns.duplicated()]

    if args.queryable_only and "ok" in out.columns:
        ok_mask = out["ok"].fillna(False)
        if isinstance(ok_mask, pd.DataFrame):
            ok_mask = ok_mask.iloc[:, 0]
        out = out.loc[ok_mask.astype(bool)].reset_index(drop=True)

    output = args.output or args.input
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    live = 0
    if "ok" in out.columns:
        ok_vals = out["ok"]
        if isinstance(ok_vals, pd.DataFrame):
            ok_vals = ok_vals.iloc[:, 0]
        live = int(ok_vals.fillna(False).astype(bool).sum())
    logger.success("Wrote {:,} rows ({:,} queryable) to {}", len(out), live, output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
