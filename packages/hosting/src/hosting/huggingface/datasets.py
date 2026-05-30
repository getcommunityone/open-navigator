"""High-level publishers for Open Navigator's gold dataset families.

Each family is published one-table-per-repo (preserving the behavior of the
legacy per-dataset scripts), built on :class:`hosting.huggingface.publisher.DatasetPublisher`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from loguru import logger

from .config import HFConfig
from .publisher import DatasetPublisher, UploadResult, dataset_name_from_stem

DEFAULT_GOLD_DIR = Path("data/gold")
DEFAULT_NATIONAL_DIR = Path("data/gold/national")
DEFAULT_STATE_SPLITS_DIR = Path("data/gold/by_state")

# family table -> gold parquet filename (relative to the gold dir).
MEETING_TABLES: dict[str, str] = {
    "calendar": "meetings_calendar.parquet",
    "transcripts": "meetings_transcripts.parquet",
    "demographics": "meetings_demographics.parquet",
    "topics": "meetings_topics.parquet",
    "decisions": "meetings_decisions.parquet",
}
CONTACTS_TABLES: dict[str, str] = {
    "local_officials": "contacts_local_officials.parquet",
    "meeting_attendance": "contacts_meeting_attendance.parquet",
    "state_legislators": "contacts_state_legislators.parquet",
    "school_board": "contacts_school_board.parquet",
}
NONPROFIT_TABLES: dict[str, str] = {
    "organizations": "nonprofits_organizations.parquet",
    "financials": "nonprofits_financials.parquet",
    "programs": "nonprofits_programs.parquet",
    "locations": "nonprofits_locations.parquet",
    "fundraisers": "nonprofits_fundraisers.parquet",
}
# national gold filename -> dataset name (under data/gold/national).
NATIONAL_DATASETS: dict[str, str] = {
    "meetings_calendar.parquet": "meetings-calendar",
    "nonprofits_organizations.parquet": "nonprofits-organizations",
    "nonprofits_financials.parquet": "nonprofits-financials",
    "nonprofits_programs.parquet": "nonprofits-programs",
    "nonprofits_locations.parquet": "nonprofits-locations",
}

US_STATES: list[str] = [
    "AA", "AE", "AK", "AL", "AP", "AR", "AS", "AZ", "CA", "CO", "CT",
    "DC", "DE", "FL", "FM", "GA", "GU", "HI", "IA", "ID", "IL", "IN",
    "KS", "KY", "LA", "MA", "MD", "ME", "MH", "MI", "MN", "MO", "MP",
    "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH",
    "OK", "OR", "PA", "PR", "PW", "RI", "SC", "SD", "TN", "TX", "UT",
    "VA", "VI", "VT", "WA", "WI", "WV", "WY",
]


def _publish_table_group(
    publisher: DatasetPublisher,
    tables: Mapping[str, str],
    repo_prefix: str,
    gold_dir: Path,
    *,
    only: Iterable[str] | None = None,
    private: bool = False,
) -> list[UploadResult]:
    only_set = set(only) if only else None
    results: list[UploadResult] = []
    for name, filename in tables.items():
        if only_set and name not in only_set:
            continue
        repo_id = f"{repo_prefix}-{name.replace('_', '-')}"
        results.append(
            publisher.publish_parquet(
                gold_dir / filename,
                repo_id,
                private=private,
                commit_message=f"Update {name} table",
            )
        )
    return results


def publish_meetings(
    publisher: DatasetPublisher,
    *,
    config: HFConfig | None = None,
    gold_dir: Path | str = DEFAULT_GOLD_DIR,
    only: Iterable[str] | None = None,
    private: bool = False,
) -> list[UploadResult]:
    config = config or publisher.config
    prefix = config.dataset_prefix_repo("meetings")
    return _publish_table_group(
        publisher, MEETING_TABLES, prefix, Path(gold_dir), only=only, private=private
    )


def publish_contacts(
    publisher: DatasetPublisher,
    *,
    config: HFConfig | None = None,
    gold_dir: Path | str = DEFAULT_GOLD_DIR,
    only: Iterable[str] | None = None,
    private: bool = False,
) -> list[UploadResult]:
    config = config or publisher.config
    prefix = config.dataset_prefix_repo("contacts")
    return _publish_table_group(
        publisher, CONTACTS_TABLES, prefix, Path(gold_dir), only=only, private=private
    )


def publish_nonprofits(
    publisher: DatasetPublisher,
    *,
    config: HFConfig | None = None,
    gold_dir: Path | str = DEFAULT_GOLD_DIR,
    only: Iterable[str] | None = None,
    private: bool = False,
) -> list[UploadResult]:
    config = config or publisher.config
    prefix = config.dataset_prefix_repo("nonprofits")
    return _publish_table_group(
        publisher, NONPROFIT_TABLES, prefix, Path(gold_dir), only=only, private=private
    )


def publish_gold_dir(
    publisher: DatasetPublisher,
    *,
    config: HFConfig | None = None,
    gold_dir: Path | str = DEFAULT_GOLD_DIR,
    only_file: str | None = None,
    max_rows: int | None = None,
    skip_large: bool = False,
    private: bool = False,
) -> list[UploadResult]:
    """Publish consolidated gold parquet files (each ``*.parquet`` -> its own dataset)."""
    config = config or publisher.config
    gold_dir = Path(gold_dir)
    if only_file:
        files = [gold_dir / only_file]
    else:
        files = sorted(gold_dir.glob("*.parquet"))
    if not files:
        logger.warning("No parquet files found in {}", gold_dir)
        return []

    results: list[UploadResult] = []
    for file_path in files:
        size_mb = file_path.stat().st_size / (1024 * 1024) if file_path.exists() else 0
        if skip_large and size_mb > 100:
            logger.info("Skipping {} ({:.1f} MB) - too large", file_path.name, size_mb)
            continue
        repo_id = config.dataset_repo_id(dataset_name_from_stem(file_path.stem))
        results.append(
            publisher.publish_parquet(
                file_path,
                repo_id,
                private=private,
                max_rows=max_rows,
                commit_message="Upload consolidated gold table",
            )
        )
    return results


def publish_national_gold(
    publisher: DatasetPublisher,
    *,
    config: HFConfig | None = None,
    gold_dir: Path | str = DEFAULT_NATIONAL_DIR,
    private: bool = False,
) -> list[UploadResult]:
    """Publish the national-level gold datasets (data/gold/national)."""
    config = config or publisher.config
    gold_dir = Path(gold_dir)
    results: list[UploadResult] = []
    for filename, name in NATIONAL_DATASETS.items():
        repo_id = config.dataset_repo_id(name)
        results.append(
            publisher.publish_parquet(
                gold_dir / filename,
                repo_id,
                private=private,
                commit_message=f"Update {name}",
            )
        )
    return results


def _split_name_for(file_stem: str, state: str) -> str:
    base = file_stem.replace(f"_{state}", "")
    for prefix in ("nonprofits_", "jurisdictions_", "domains_"):
        base = base.replace(prefix, "")
    return base


def publish_state_splits(
    publisher: DatasetPublisher,
    *,
    config: HFConfig | None = None,
    splits_dir: Path | str = DEFAULT_STATE_SPLITS_DIR,
    states: Iterable[str] | None = None,
    dry_run: bool = False,
    private: bool = False,
) -> dict[str, bool]:
    """Publish per-state split files; each state gets one ``<prefix>-data-<STATE>`` repo."""
    config = config or publisher.config
    prefix = config.dataset_prefix_repo("data")
    splits_dir = Path(splits_dir)

    if states is None:
        discovered = {
            f.stem[-2:]
            for f in splits_dir.glob("*_??.parquet")
            if f.stem[-2:] in US_STATES
        }
        states = sorted(discovered)
        logger.info("Found data for {} states/territories", len(states))

    results: dict[str, bool] = {}
    for raw_state in states:
        state = raw_state.upper()
        files = sorted(splits_dir.glob(f"*_{state}.parquet"))
        repo_id = f"{prefix}-{state}"
        if not files:
            logger.warning("No files found for state: {}", state)
            results[state] = False
            continue
        if dry_run:
            logger.info("[dry-run] {} <- {} file(s)", repo_id, len(files))
            results[state] = True
            continue
        publisher.ensure_repo(repo_id, private=private)
        ok = True
        for file_path in files:
            split_name = _split_name_for(file_path.stem, state)
            result = publisher.publish_parquet(file_path, repo_id, split=split_name)
            ok = ok and result.ok
        results[state] = ok
    return results


def publish_discovery(
    publisher: DatasetPublisher,
    repo_id: str,
    *,
    data_dir: Path | str = Path("data/bronze/discovered_sources"),
    private: bool = False,
) -> UploadResult:
    """Combine ``discovery_*.csv`` files, de-duplicate, and push as the ``discovery`` split."""
    import pandas as pd

    data_dir = Path(data_dir)
    url = f"https://huggingface.co/datasets/{repo_id}"
    if not data_dir.exists():
        logger.error("Directory not found: {}", data_dir)
        return UploadResult(repo_id=repo_id, url=url, error="Directory not found")

    csv_files = sorted(data_dir.glob("discovery_*.csv"))
    if not csv_files:
        logger.warning("No discovery CSV files found in {}", data_dir)
        return UploadResult(repo_id=repo_id, url=url, error="No discovery CSV files")

    combined = pd.concat(
        (pd.read_csv(f) for f in csv_files), ignore_index=True
    ).drop_duplicates(subset=["name", "state"], keep="last")
    logger.info("Combined {:,} jurisdictions from {} files", len(combined), len(csv_files))
    return publisher.publish_dataframe(
        combined,
        repo_id,
        split="discovery",
        private=private,
        commit_message="Update discovery results",
    )
