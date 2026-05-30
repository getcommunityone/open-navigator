"""Core HuggingFace dataset-publishing primitives.

Consolidates the upload logic that was duplicated across the legacy
``upload_to_huggingface.py``, ``upload_consolidated_gold.py``,
``publish_gold_datasets.py``, ``upload_meetings_to_hf.py``,
``upload_nonprofits_to_hf.py`` and ``upload_state_splits_to_hf.py`` scripts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from .config import HFConfig

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd

# file-stem -> friendly dataset name overrides (from upload_consolidated_gold.py).
GOLD_NAME_SIMPLIFICATIONS: dict[str, str] = {
    "bills_bills": "bills",
    "bills_bill_actions": "bill-actions",
    "bills_bill_sponsorships": "bill-sponsorships",
    "contact_official": "officials",
    "contacts_local_officials": "local-officials",
    "events_participants": "event-participants",
    "events_documents": "event-documents",
}


def dataset_name_from_stem(file_stem: str) -> str:
    """Convert a parquet file stem to a HuggingFace dataset name.

    Examples: ``bills_bills`` -> ``bills``; ``nonprofits_organizations`` ->
    ``nonprofits-organizations``.
    """
    if file_stem in GOLD_NAME_SIMPLIFICATIONS:
        return GOLD_NAME_SIMPLIFICATIONS[file_stem]
    return file_stem.replace("_", "-")


@dataclass
class UploadResult:
    """Outcome of a single dataset upload."""

    repo_id: str
    url: str
    records: int = 0
    columns: int = 0
    size_mb: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class DatasetPublisher:
    """Publish pandas DataFrames / parquet / CSV / JSON to HuggingFace Datasets."""

    def __init__(self, config: HFConfig | None = None, *, login_now: bool = True):
        self.config = config or HFConfig()
        self.token = self.config.require_token()

        from huggingface_hub import HfApi, login

        if login_now:
            login(token=self.token)
            logger.info("Logged in to HuggingFace")
        self.api = HfApi(token=self.token)

    # -- repo helpers ----------------------------------------------------
    def ensure_repo(
        self, repo_id: str, *, repo_type: str = "dataset", private: bool = False
    ) -> None:
        """Create the repo if it does not already exist (idempotent)."""
        from huggingface_hub import create_repo

        try:
            create_repo(
                repo_id=repo_id,
                repo_type=repo_type,
                private=private,
                exist_ok=True,
                token=self.token,
            )
            logger.debug("Repository ready: {}", repo_id)
        except Exception as exc:  # noqa: BLE001 - matches legacy best-effort behavior
            logger.debug("Repo create skipped for {}: {}", repo_id, exc)

    # -- core upload -----------------------------------------------------
    def publish_dataframe(
        self,
        df: "pd.DataFrame",
        repo_id: str,
        *,
        split: str | None = None,
        private: bool = False,
        commit_message: str | None = None,
    ) -> UploadResult:
        """Push a DataFrame to ``repo_id`` (one parquet shard, never per-row files)."""
        from datasets import Dataset

        url = f"https://huggingface.co/datasets/{repo_id}"
        try:
            self.ensure_repo(repo_id, private=private)
            dataset = Dataset.from_pandas(df)
            kwargs: dict = {
                "repo_id": repo_id,
                "private": private,
                "token": self.token,
                "commit_message": commit_message
                or f"Update dataset - {datetime.now():%Y-%m-%d %H:%M:%S}",
            }
            if split:
                kwargs["split"] = split
            dataset.push_to_hub(**kwargs)
            logger.success("Uploaded {:,} records to {}", len(df), url)
            return UploadResult(
                repo_id=repo_id, url=url, records=len(df), columns=len(df.columns)
            )
        except Exception as exc:  # noqa: BLE001 - collected into the run summary
            logger.error("Upload to {} failed: {}", repo_id, exc)
            return UploadResult(repo_id=repo_id, url=url, error=str(exc))

    def publish_parquet(
        self,
        path: Path | str,
        repo_id: str,
        *,
        split: str | None = None,
        private: bool = False,
        max_rows: int | None = None,
        commit_message: str | None = None,
    ) -> UploadResult:
        """Read a parquet file and publish it; ``max_rows`` truncates for testing."""
        import pandas as pd

        path = Path(path)
        url = f"https://huggingface.co/datasets/{repo_id}"
        if not path.exists():
            logger.warning("Skipping {} - file not found", path)
            return UploadResult(repo_id=repo_id, url=url, error="File not found")

        size_mb = path.stat().st_size / (1024 * 1024)
        df = pd.read_parquet(path)
        if max_rows and len(df) > max_rows:
            logger.info("Limiting to {:,} rows (testing mode)", max_rows)
            df = df.head(max_rows)
        logger.info(
            "Uploading {} ({:.1f} MB, {:,} rows) -> {}",
            path.name,
            size_mb,
            len(df),
            repo_id,
        )
        result = self.publish_dataframe(
            df, repo_id, split=split, private=private, commit_message=commit_message
        )
        result.size_mb = size_mb
        return result

    def publish_file(
        self,
        path: Path | str,
        repo_id: str,
        *,
        split: str | None = None,
        private: bool = False,
        commit_message: str | None = None,
    ) -> UploadResult:
        """Publish a ``.parquet`` / ``.csv`` / ``.json`` tabular file."""
        import pandas as pd

        path = Path(path)
        url = f"https://huggingface.co/datasets/{repo_id}"
        if not path.exists():
            logger.error("File not found: {}", path)
            return UploadResult(repo_id=repo_id, url=url, error="File not found")

        suffix = path.suffix.lower()
        if suffix == ".parquet":
            df = pd.read_parquet(path)
        elif suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix == ".json":
            df = pd.read_json(path)
        else:
            logger.error("Unsupported file type: {} (use .parquet/.csv/.json)", suffix)
            return UploadResult(
                repo_id=repo_id, url=url, error=f"Unsupported file type: {suffix}"
            )
        return self.publish_dataframe(
            df, repo_id, split=split, private=private, commit_message=commit_message
        )

    def upload_readme(
        self, repo_id: str, markdown: str, *, repo_type: str = "dataset"
    ) -> None:
        """Upload a README/dataset card to ``repo_id``."""
        self.ensure_repo(repo_id, repo_type=repo_type)
        self.api.upload_file(
            path_or_fileobj=markdown.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type=repo_type,
            token=self.token,
        )
        logger.success("README uploaded to {}", repo_id)


def summarize(results: list[UploadResult]) -> tuple[int, int, int]:
    """Log a success/failure summary; return (n_ok, n_failed, total_records)."""
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    for r in ok:
        logger.info("  OK  {} ({:,} records) -> {}", r.repo_id, r.records, r.url)
    for r in failed:
        logger.error("  ERR {}: {}", r.repo_id, r.error)
    total = sum(r.records for r in ok)
    logger.info(
        "Published {} dataset(s), {} failed, {:,} total records",
        len(ok),
        len(failed),
        total,
    )
    return len(ok), len(failed), total
