"""
Sync / fetch meeting transcript JSON in Azure Blob Storage (#630).

Private container; object key ``transcripts/{video_id}.json``.
Credentials from env (never committed):

  AZURE_STORAGE_CONNECTION_STRING  (preferred)
  or AZURE_STORAGE_ACCOUNT_URL + DefaultAzureCredential
  AZURE_TRANSCRIPT_CONTAINER       (default: transcripts)

Install optional extra: ``pip install 'communityone-hosting[azure]'``
(or ``azure-storage-blob``).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from loguru import logger

DEFAULT_CONTAINER = "transcripts"
BLOB_PREFIX = "transcripts/"


def blob_name_for_video(video_id: str) -> str:
    vid = (video_id or "").strip()
    if not vid or "/" in vid or ".." in vid:
        raise ValueError("invalid video_id")
    return f"{BLOB_PREFIX}{vid}.json"


def _container_name() -> str:
    return (os.environ.get("AZURE_TRANSCRIPT_CONTAINER") or DEFAULT_CONTAINER).strip()


def _blob_service_client():
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "azure-storage-blob is required. "
            "Install with: pip install 'communityone-hosting[azure]'"
        ) from exc

    conn = (os.environ.get("AZURE_STORAGE_CONNECTION_STRING") or "").strip()
    if conn:
        return BlobServiceClient.from_connection_string(conn)

    account_url = (os.environ.get("AZURE_STORAGE_ACCOUNT_URL") or "").strip()
    if not account_url:
        raise RuntimeError(
            "Set AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_URL"
        )
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "azure-identity is required for account-URL auth. "
            "Install communityone-hosting[azure]."
        ) from exc
    return BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())


def upload_transcript_file(video_id: str, path: Path, *, overwrite: bool = True) -> str:
    """Upload one local transcript JSON; returns the blob name."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    name = blob_name_for_video(video_id)
    client = _blob_service_client()
    blob = client.get_blob_client(container=_container_name(), blob=name)
    data = path.read_bytes()
    blob.upload_blob(data, overwrite=overwrite, content_type="application/json")
    logger.success("Uploaded transcript {} -> {}", video_id, name)
    return name


def download_transcript_json(video_id: str) -> Optional[dict[str, Any]]:
    """Fetch one transcript JSON by video_id, or None if missing."""
    name = blob_name_for_video(video_id)
    client = _blob_service_client()
    blob = client.get_blob_client(container=_container_name(), blob=name)
    try:
        raw = blob.download_blob().readall()
    except Exception as exc:  # noqa: BLE001
        # ResourceNotFoundError and friends
        if "BlobNotFound" in type(exc).__name__ or "404" in str(exc):
            return None
        raise
    return json.loads(raw.decode("utf-8"))


def sync_local_cache_dir(
    cache_root: Path,
    *,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Walk ``gemini_transcript_policy/**/01_transcripts/*.json`` and upload by video_id.

    Expects each file to contain ``youtube.video_id`` or top-level ``video_id``.
    """
    cache_root = Path(cache_root)
    uploaded = skipped = errors = 0
    paths = sorted(cache_root.glob("**/01_transcripts/*.json"))
    if limit is not None:
        paths = paths[: max(0, limit)]
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            video_id = (
                (payload.get("youtube") or {}).get("video_id")
                or payload.get("video_id")
                or ""
            )
            video_id = str(video_id).strip()
            if not video_id:
                skipped += 1
                continue
            if dry_run:
                logger.info("dry-run would upload {} <- {}", video_id, path)
                uploaded += 1
                continue
            upload_transcript_file(video_id, path)
            uploaded += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.error("sync failed for {}: {}", path, exc)
    logger.info(
        "Azure transcript sync: uploaded={} skipped={} errors={}",
        uploaded,
        skipped,
        errors,
    )
    return {"uploaded": uploaded, "skipped": skipped, "errors": errors}


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Sync local transcript cache to Azure Blob (#630)")
    p.add_argument(
        "--cache-root",
        type=Path,
        default=Path("data/cache/gemini_transcript_policy"),
        help="Root of gemini_transcript_policy cache",
    )
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    sync_local_cache_dir(args.cache_root, limit=args.limit, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
