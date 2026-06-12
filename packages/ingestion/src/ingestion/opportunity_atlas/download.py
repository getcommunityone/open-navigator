"""Download the Opportunity Atlas commuting-zone outcomes CSV.

Streams ``cz_outcomes.csv`` (~58 MB) from Opportunity Insights to a local cache
file under ``data/cache/opportunity_atlas/`` so the 58 MB raw is NOT committed.
The download is streamed (never held fully in memory) and skipped if a complete
cached copy already exists (use ``--force`` to re-fetch).

Source:
    Opportunity Insights — "Opportunity Atlas" / Chetty, Hendren, Jones & Porter
    (2018), "Race and Economic Opportunity in the United States."
    https://opportunityinsights.org/wp-content/uploads/2018/10/cz_outcomes.csv
"""

from __future__ import annotations

from pathlib import Path

import httpx
from loguru import logger

CZ_OUTCOMES_URL = (
    "https://opportunityinsights.org/wp-content/uploads/2018/10/cz_outcomes.csv"
)

# Cache under data/cache (NEVER deleted per CLAUDE.md; the 58 MB file stays here
# and out of git — ensure data/cache is gitignored, which it is repo-wide).
DEFAULT_CACHE_DIR = Path("data/cache/opportunity_atlas")
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "cz_outcomes.csv"

# The source is ~58 MB; treat anything materially smaller as a truncated/failed
# download and re-fetch rather than parse a partial file.
_MIN_EXPECTED_BYTES = 50 * 1024 * 1024


def download_cz_outcomes(
    dest: Path = DEFAULT_CACHE_FILE,
    *,
    force: bool = False,
    timeout: float = 300.0,
) -> Path:
    """Stream the CZ outcomes CSV to ``dest``; return the local path.

    Args:
        dest: Local cache path to write to.
        force: Re-download even if a complete cached copy exists.
        timeout: HTTP read timeout (seconds); the file is large.

    Returns:
        Path to the cached CSV.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        size = dest.stat().st_size
        if size >= _MIN_EXPECTED_BYTES:
            logger.info(
                "Using cached Opportunity Atlas CSV: {} ({:,} bytes)", dest, size
            )
            return dest
        logger.warning(
            "Cached file {} looks truncated ({:,} bytes < {:,}); re-downloading.",
            dest,
            size,
            _MIN_EXPECTED_BYTES,
        )

    tmp = dest.with_suffix(dest.suffix + ".part")
    logger.info("Downloading Opportunity Atlas CZ outcomes from {}", CZ_OUTCOMES_URL)
    written = 0
    with httpx.stream(
        "GET",
        CZ_OUTCOMES_URL,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "open-navigator/1.0 (civic data platform)"},
    ) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                fh.write(chunk)
                written += len(chunk)
                if written % (10 * 1024 * 1024) < (1024 * 256):
                    logger.info("  ... {:,} MB", written // (1024 * 1024))

    if written < _MIN_EXPECTED_BYTES:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded only {written:,} bytes (expected >= {_MIN_EXPECTED_BYTES:,}); "
            "the source may be unavailable or truncated."
        )

    tmp.replace(dest)
    logger.success("Downloaded {:,} bytes -> {}", written, dest)
    return dest
