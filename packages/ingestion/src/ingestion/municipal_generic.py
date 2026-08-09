import argparse
import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import List, Optional, Any

# Ensure the root package is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import httpx
from pydantic import BaseModel, Field, field_validator, HttpUrl
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Assuming CommunityOne standard models are accessible
from packages.datamodels.models.meeting_event import (
    MeetingEvent, 
    Classification, 
    EventStatus, 
    Location, 
    Link
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    
    # Coordinates validation
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    location_name: Optional[str] = Field(default="TBD")
    
    # Example video URL if provided
    video_url: Optional[HttpUrl] = None

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, v: str) -> str:
        return v.strip()


# ==========================================
# 2. Robust HTTP Client
# ==========================================

class AsyncMunicipalClient:
    """
    An HTTP client for municipal scraping with robust error handling,
    exponential backoff, and concurrency/rate-limiting.
    """
    def __init__(self, base_url: str, max_concurrent: int = 5, requests_per_second: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(15.0),
            headers={"User-Agent": "CommunityOne-Civic-Ingestion-Bot/1.0"}
        )
        # Concurrency limit
        self.semaphore = asyncio.Semaphore(max_concurrent)
        # Rate limiting delay
        self.rate_limit_delay = 1.0 / requests_per_second

    async def close(self):
        await self.client.aclose()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True
    )
    async def _fetch_with_retry(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """Internal fetcher with exponential backoff on transient failures."""
        async with self.semaphore:
            logger.info(f"Fetching {endpoint} with params {params}")
            response = await self.client.get(endpoint, params=params)
            response.raise_for_status()
            
            # Rate limiting sleep
            await asyncio.sleep(self.rate_limit_delay)
            return response.json()

    async def fetch_agendas(self, year: int, month: int) -> List[RawMunicipalMeeting]:
        """Fetch raw meetings and validate via Pydantic."""
        try:
            # Assumes endpoint structure like /api/meetings
            data = await self._fetch_with_retry("/api/meetings", params={"year": year, "month": month})
            
            # Validate payloads strictly
            validated_meetings = [RawMunicipalMeeting(**item) for item in data.get("meetings", [])]
            return validated_meetings
        except Exception as e:
            logger.error(f"Failed to fetch or validate agendas: {e}")
            return []


# ==========================================
# 3. ETL Transformation
# ==========================================

def transform_to_standard_model(
    raw: RawMunicipalMeeting, 
    municipality: str, 
    state: str,
    base_url: str
) -> MeetingEvent:
    """Transforms the generic raw payload into the CommunityOne MeetingEvent model."""
    
    # Map title to Classification
    classification = Classification.NOT_CLASSIFIED
    title_lower = raw.title.lower()
    if "council" in title_lower:
        classification = Classification.COUNCIL
    elif "board" in title_lower:
        classification = Classification.BOARD
    elif "committee" in title_lower:
        classification = Classification.COMMITTEE

    # Create location
    loc_name = raw.location_name if raw.location_name != "TBD" else f"{municipality} City Hall"
    location = Location(name=loc_name, city=municipality, state=state)
    
    # Initialize MeetingEvent
    event = MeetingEvent(
        title=raw.title,
        description=f"{municipality} {raw.title}",
        classification=classification,
        start=raw.meeting_date,
        status=EventStatus.CONFIRMED if raw.status.lower() == "confirmed" else EventStatus.TENTATIVE,
        location=location,
        source=f"{base_url}/meetings/{raw.id}",
        jurisdiction_name=municipality,
        state_code=state
    )
    
    # Attach Links
    if raw.agenda_html:
        # Check if it's a direct URL or embedded HTML.
        href = raw.agenda_html if raw.agenda_html.startswith("http") else f"{base_url}/agenda/{raw.id}"
        event.add_link(title="Agenda", href=href)
    
    if raw.video_url:
        event.add_link(title="Video Recording", href=str(raw.video_url), content_type="video/mp4")
        
    return event


# ==========================================
# 4. Main Pipeline Execution
# ==========================================

async def main(args: argparse.Namespace):
    logger.info(f"Starting Agenda Ingestion Pipeline for {args.municipality}, {args.state}")
    
    client = AsyncMunicipalClient(base_url=args.endpoint_url)
    try:
        # 1. Extract & Validate (Pydantic)
        raw_meetings = await client.fetch_agendas(year=datetime.now().year, month=datetime.now().month)
        logger.info(f"Successfully extracted and validated {len(raw_meetings)} meetings.")
        
        # 2. Transform (ETL Mapping)
        standardized_events = [
            transform_to_standard_model(m, args.municipality, args.state, args.endpoint_url) 
            for m in raw_meetings
        ]
        
        # 3. Load (Integration with DB/Delta Lake)
        for event in standardized_events:
            logger.info(f"Processed Standardized Event: {event.title} on {event.start}")
            # Insert loading logic here (e.g. inserting to Postgres or writing to Parquet)
            
    finally:
        await client.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest municipal meeting agendas from a generic endpoint.")
    parser.add_argument("--state", required=True, help="State abbreviation (e.g., IN)")
    parser.add_argument("--municipality", required=True, help="Municipality name (e.g., 'Westfield')")
    parser.add_argument("--endpoint-url", required=True, help="Base URL of the municipal API endpoint (e.g., 'https://mock.westfield.in.gov')")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
