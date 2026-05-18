#!/usr/bin/env python3
"""
Export ``public.jurisdiction_mapping_analysis`` (dbt mart) to Parquet and publish on Hugging Face.

Requires the mart table built:

  ./scripts/dbt.sh run --select jurisdiction_mapping_analysis

Usage (open-navigator repo root):

  export HF_TOKEN=hf_...
  .venv/bin/python scripts/datasources/jurisdictions/publish_jurisdiction_mapping_analysis_to_hf.py

  # Custom repo (default: CommunityOne/one-jurisdiction-mapping-analysis)
  .venv/bin/python scripts/datasources/jurisdictions/publish_jurisdiction_mapping_analysis_to_hf.py \\
    --repo-id CommunityOne/one-jurisdiction-mapping-analysis
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TABLE = "public.jurisdiction_mapping_analysis"
DEFAULT_SPLIT = "jurisdiction_mapping_analysis"


def _db_url() -> str:
    load_dotenv(ROOT / ".env")
    return (
        (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
        or (os.getenv("NEON_DATABASE_URL_DEV") or "").strip()
        or (os.getenv("NEON_DATABASE_URL") or "").strip()
        or (os.getenv("DATABASE_URL") or "").strip()
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def _default_repo_id() -> str:
    org = (os.getenv("HF_ORGANIZATION") or "CommunityOne").strip()
    prefix = (os.getenv("HF_DATASET_PREFIX") or "one").strip()
    name = (os.getenv("HF_JURISDICTION_MAPPING_ANALYSIS_DATASET") or "jurisdiction-mapping-analysis").strip()
    slug = f"{prefix}-{name}" if prefix else name
    return f"{org}/{slug}" if org else slug


def _fetch_dataframe() -> pd.DataFrame:
    url = _db_url()
    conn = psycopg2.connect(url)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM {TABLE} ORDER BY jurisdiction_id")
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        raise RuntimeError(f"{TABLE} is empty — run dbt: ./scripts/dbt.sh run --select jurisdiction_mapping_analysis")

    df = pd.DataFrame([dict(r) for r in rows])
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = pd.to_datetime(df[col], utc=True)
        elif df[col].map(lambda x: isinstance(x, Decimal)).any():
            df[col] = df[col].apply(
                lambda x: int(x) if isinstance(x, Decimal) and x == x.to_integral_value() else float(x)
                if isinstance(x, Decimal)
                else x
            )
    return df


def _dataset_readme(repo_id: str, row_count: int, generated_at: str) -> str:
    return f"""---
license: cc-by-4.0
task_categories:
  - text-classification
language:
  - en
tags:
  - government
  - jurisdictions
  - open-data
size_categories:
  - 10K<n<100K
---

# Jurisdiction mapping analysis

One row per U.S. local-government jurisdiction (county, municipality, school district, state) with the
**primary website** chosen from NACO, USCM, NCES, GSA, league, and override sources — same logic as
``dbt_project/models/marts/jurisdiction_mapping_analysis.sql`` in [open-navigator](https://github.com/getcommunityone/open-navigator).

## Schema

| Column | Description |
|--------|-------------|
| `jurisdiction_id` | Stable id (e.g. `county_01125`) |
| `name`, `state_code`, `jurisdiction_type` | Identity |
| `primary_website_url`, `primary_website_source` | Winning portal URL and source |
| `has_*_source` | Directory coverage flags |
| `primary_url_syntax_ok`, `primary_url_passes_basic_checks` | Static URL QA (not HTTP reachability) |
| `acs_population_tier`, `acs_income_level` | ACS demographics when joined |

## Load

```python
from datasets import load_dataset

ds = load_dataset("{repo_id}", split="{DEFAULT_SPLIT}")
# or
import pandas as pd
df = pd.read_parquet("hf://datasets/{repo_id}/{DEFAULT_SPLIT}/0000.parquet")
```

## Provenance

- **Rows:** {row_count:,}
- **Generated:** {generated_at}
- **Source table:** `{TABLE}`
"""


def publish(
    *,
    repo_id: str,
    private: bool = False,
    split: str = DEFAULT_SPLIT,
    parquet_dir: Path | None = None,
) -> str:
    from datasets import Dataset
    from huggingface_hub import HfApi, create_repo, login

    token = (os.getenv("HF_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("HF_TOKEN required — https://huggingface.co/settings/tokens")

    login(token=token)
    create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)

    df = _fetch_dataframe()
    generated_at = datetime.now(timezone.utc).isoformat()

    out_dir = parquet_dir or (ROOT / "data" / "exports" / "jurisdiction_mapping_analysis")
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "jurisdiction_mapping_analysis.parquet"
    df.to_parquet(parquet_path, index=False, compression="snappy")
    print(f"Wrote {parquet_path} ({parquet_path.stat().st_size / (1024 * 1024):.2f} MB, {len(df):,} rows)")

    dataset = Dataset.from_pandas(df, preserve_index=False)
    dataset.push_to_hub(
        repo_id,
        split=split,
        commit_message=f"Update {TABLE} ({len(df):,} rows)",
        private=private,
    )

    readme = _dataset_readme(repo_id, len(df), generated_at)
    api = HfApi()
    api.upload_file(
        path_or_fileobj=readme.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Dataset card",
    )

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"Published → {url} (split={split!r})")
    return url


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Publish {TABLE} to Hugging Face as Parquet")
    parser.add_argument(
        "--repo-id",
        default=os.getenv("HF_JURISDICTION_MAPPING_ANALYSIS_REPO") or _default_repo_id(),
        help="HF dataset repo id (org/name)",
    )
    parser.add_argument("--private", action="store_true", help="Private dataset (default: public)")
    parser.add_argument("--split", default=DEFAULT_SPLIT, help="Dataset split name on the Hub")
    parser.add_argument(
        "--parquet-only",
        action="store_true",
        help="Write local Parquet only; do not upload",
    )
    parser.add_argument(
        "--parquet-dir",
        type=Path,
        default=None,
        help="Local export directory (default: data/exports/jurisdiction_mapping_analysis)",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    if args.parquet_only:
        df = _fetch_dataframe()
        out_dir = args.parquet_dir or (ROOT / "data" / "exports" / "jurisdiction_mapping_analysis")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "jurisdiction_mapping_analysis.parquet"
        df.to_parquet(path, index=False, compression="snappy")
        print(f"Wrote {path} ({len(df):,} rows)")
        return 0

    publish(
        repo_id=args.repo_id.strip(),
        private=args.private,
        split=args.split.strip(),
        parquet_dir=args.parquet_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
