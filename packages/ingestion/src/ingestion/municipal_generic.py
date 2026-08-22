"""Generic municipal meeting agenda ingestion pipeline.

Extracts meeting agendas from a municipality's API, validates them with
Pydantic, transforms into the CommunityOne MeetingEvent standard model,
and persists to the bronze layer as Parquet for dbt promotion.

Usage:
    python -m ingestion.municipal_generic \
        --state IN \
        --municipality Westfield \
        --endpoint-url https://mock.westfield.in.gov
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any

import httpx
import pandas as pd
from loguru import logger
from pydantic import BaseModel, Field, field_validator, HttpUrl
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from models.meeting_event import (
    MeetingEvent,
    Classification,
    EventStatus,
    Location,
    Link,
)

# Bronze output directory — relative to the repo root, matching the
# established ``data/bronze/<source>/`` convention.
_BRONZE_DIR = Path(__file__).resolve().parents[4] / "data" / "bronze" / "municipal_meetings"


# ==========================================
# 1. Pydantic Validation Models
# ==========================================

class RawMunicipalMeeting(BaseModel):
    """Strict validation for the raw payload expected from generic municipal APIs."""

    id: str = Field(..., description="Unique meeting identifier from the source")
    title: str = Field(..., description="Meeting title (e.g., 'City Council Regular Meeting')")
    meeting_date: datetime = Field(..., description="ISO 8601 formatted date and time")
    agenda_html: str = Field(..., description="Raw HTML string or link to the agenda")
    status: str = Field(default="confirmed")

    # Coordinates — optional; only populated when the source provides them.
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)

    # Location name is NULL when the source doesn't provide it — never fabricated.
    location_name: Optional[str] = Field(default=None)

    # Video URL if the source provides one.
    video_url: Optional[HttpUrl] = None

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, v: str) -> str:
        return v.strip()


# ==========================================
# 2. Robust HTTP Client
# ==========================================

class AsyncMunicipalClient:
    """HTTP client for municipal scraping with exponential backoff,
    concurrency limiting, and rate-limit enforcement."""

    def __init__(self, base_url: str, max_concurrent: int = 5, requests_per_second: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(15.0),
            headers={"User-Agent": "CommunityOne-Civic-Ingestion-Bot/1.0"},
        )
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limit_delay = 1.0 / requests_per_second

    async def close(self):
        await self.client.aclose()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _fetch_with_retry(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """Internal fetcher with exponential backoff on transient failures."""
        async with self.semaphore:
            logger.info("Fetching {} with params {}", endpoint, params)
            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()
            await asyncio.sleep(self.rate_limit_delay)
            return response.json()

    async def fetch_agendas(self, year: int, month: int) -> List[RawMunicipalMeeting]:
        """Fetch raw meetings and validate via Pydantic."""
        try:
            data = await self._fetch_with_retry("/api/meetings", params={"year": year, "month": month})
            validated_meetings = [RawMunicipalMeeting(**item) for item in data.get("meetings", [])]
            return validated_meetings
        except Exception:
            logger.exception("Failed to fetch or validate agendas")
            return []


# ==========================================
# 3. ETL Transformation
# ==========================================

def transform_to_standard_model(
    raw: RawMunicipalMeeting,
    municipality: str,
    state: str,
    base_url: str,
) -> MeetingEvent:
    """Transforms the raw payload into the CommunityOne MeetingEvent model.

    Location name is left as-is from the source.  When the source does not
    provide a location name the field stays ``None`` — the transform never
    fabricates venue names.
    """

    # Map title keywords to Classification enum
    classification = Classification.NOT_CLASSIFIED
    title_lower = raw.title.lower()
    if "council" in title_lower:
        classification = Classification.COUNCIL
    elif "board" in title_lower:
        classification = Classification.BOARD
    elif "committee" in title_lower:
        classification = Classification.COMMITTEE

    # Build location from source data only — no fabrication
    location = Location(
        name=raw.location_name if raw.location_name else "Unknown",
        city=municipality,
        state=state,
    )

    event = MeetingEvent(
        title=raw.title,
        description=f"{municipality} {raw.title}",
        classification=classification,
        start=raw.meeting_date,
        status=EventStatus.CONFIRMED if raw.status.lower() == "confirmed" else EventStatus.TENTATIVE,
        location=location,
        source=f"{base_url}/meetings/{raw.id}",
        jurisdiction_name=municipality,
        state_code=state,
    )

    # Attach links — content_type is inferred by Link.__post_init__
    if raw.agenda_html:
        href = raw.agenda_html if raw.agenda_html.startswith("http") else f"{base_url}/agenda/{raw.id}"
        event.add_link(title="Agenda", href=href)

    if raw.video_url:
        event.add_link(title="Video Recording", href=str(raw.video_url))

    return event


# ==========================================
# 4. Bronze Layer Loader (Parquet)
# ==========================================

def _event_to_row(event: MeetingEvent) -> dict:
    """Flatten a MeetingEvent into a dict suitable for a DataFrame row."""
    return {
        "event_id": event.id,
        "title": event.title,
        "description": event.description,
        "classification": event.classification.value,
        "start": event.start,
        "end": event.end,
        "status": event.status.value,
        "location_name": event.location.name if event.location else None,
        "location_city": event.location.city if event.location else None,
        "location_state": event.location.state if event.location else None,
        "source": event.source,
        "jurisdiction_name": event.jurisdiction_name,
        "state_code": event.state_code,
        "scraped_at": event.scraped_at,
    }


def load_to_bronze(events: List[MeetingEvent], state: str, municipality: str) -> Path:
    """Persist transformed events to the bronze layer as Parquet.

    Files land at ``data/bronze/municipal_meetings/<ST>/<municipality>_<ts>.parquet``,
    following the repo's established ``data/bronze/<source>/`` convention.
    The dbt bronze layer picks these up for promotion to gold.
    """
    if not events:
        logger.warning("No events to load — skipping bronze write")
        return _BRONZE_DIR

    rows = [_event_to_row(e) for e in events]
    df = pd.DataFrame(rows)

    output_dir = _BRONZE_DIR / state.upper()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized_name = municipality.lower().replace(" ", "_")
    output_path = output_dir / f"{sanitized_name}_{timestamp}.parquet"

    df.to_parquet(output_path, index=False, engine="pyarrow", compression="snappy")
    logger.success("Wrote {} events to {}", len(df), output_path)
    return output_path


# ==========================================
# 5. Main Pipeline Execution
# ==========================================

async def main(args: argparse.Namespace):
    logger.info("Starting Agenda Ingestion Pipeline for {}, {}", args.municipality, args.state)

    client = AsyncMunicipalClient(base_url=args.endpoint_url)
    try:
        # Extract & Validate (Pydantic)
        raw_meetings = await client.fetch_agendas(year=datetime.now().year, month=datetime.now().month)
        logger.info("Extracted and validated {} meetings", len(raw_meetings))

        # Transform (ETL Mapping)
        standardized_events = [
            transform_to_standard_model(m, args.municipality, args.state, args.endpoint_url)
            for m in raw_meetings
        ]

        # Load (Bronze Parquet)
        output = load_to_bronze(standardized_events, args.state, args.municipality)
        logger.info("Pipeline complete — output: {}", output)

    finally:
        await client.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingest municipal meeting agendas from a generic endpoint.",
    )
    parser.add_argument("--state", required=True, help="State abbreviation (e.g., IN)")
    parser.add_argument("--municipality", required=True, help="Municipality name (e.g., 'Westfield')")
    parser.add_argument(
        "--endpoint-url",
        required=True,
        help="Base URL of the municipal API endpoint (e.g., 'https://mock.westfield.in.gov')",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
