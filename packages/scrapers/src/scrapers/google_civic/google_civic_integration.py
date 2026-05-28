"""
Google Civic Information API Integration

Supported endpoints (Representatives API was turned down April 2025):
- **Elections** (`/elections`) — upcoming election calendar metadata
- **Voter Info** (`/voterinfo`) — VIP polling places, contests, candidates, referendums
- **Divisions by address** (`/divisionsByAddress`) — OCD division IDs for an address

API Docs: https://developers.google.com/civic-information
"""
import asyncio
import re
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from loguru import logger

try:
    from pyspark.sql import SparkSession
    from config.settings import settings
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    settings = None
    logger.warning("Running without Spark/settings - limited functionality")


# Census Gazetteer names often append LSAD descriptors ("Abbeville city") that cause
# Google Civic address geocoding to fail. Strip them before querying.
_CENSUS_LSAD_SUFFIX_RE = re.compile(
    r"\s+(city|town|village|borough|township|cdp|municipality|parish|consolidated government)\s*$",
    re.IGNORECASE,
)
_PAREN_QUALIFIER_RE = re.compile(r"\s*\([^)]*\)")


def normalize_civic_place_name(name: str) -> str:
    """Drop Census LSAD tokens and parenthetical qualifiers from a place label."""
    place = re.sub(r"\s+", " ", (name or "").strip())
    place = _PAREN_QUALIFIER_RE.sub(" ", place)
    place = _CENSUS_LSAD_SUFFIX_RE.sub("", place)
    place = re.sub(r"\s+", " ", place).strip(" ,")
    return place or (name or "").strip()


def format_civic_address_query(place_name: str, state_code: str) -> str:
    """Build ``Place, ST`` suitable for Civic address= query parameters."""
    place = normalize_civic_place_name(place_name)
    state = (state_code or "").strip().upper()
    return f"{place}, {state}"


def normalize_civic_address(address: str) -> str:
    """Normalize a full ``place, ST`` string (idempotent)."""
    address = re.sub(r"\s+", " ", (address or "").strip())
    m = re.match(r"^(.+?),\s*([A-Za-z]{2})\s*$", address)
    if not m:
        return address
    return format_civic_address_query(m.group(1), m.group(2))


def civic_elections_url(*, include_key: bool = False, api_key: str | None = None) -> str:
    url = f"{GoogleCivicAPI.BASE_URL}/elections"
    if include_key and api_key:
        url += f"?key={api_key}"
    return url


def civic_voterinfo_url(
    address: str,
    *,
    election_id: str | None = None,
    include_key: bool = False,
    api_key: str | None = None,
) -> str:
    q = quote(normalize_civic_address(address), safe=",")
    url = f"{GoogleCivicAPI.BASE_URL}/voterinfo?address={q}"
    if election_id:
        url += f"&electionId={quote(str(election_id), safe='')}"
    if include_key and api_key:
        url += f"&key={api_key}"
    return url


def civic_divisions_by_address_url(address: str, *, include_key: bool = False, api_key: str | None = None) -> str:
    """Canonical divisionsByAddress URL for cache/debug (never log bare API keys by default)."""
    q = quote(normalize_civic_address(address), safe=",")
    url = f"{GoogleCivicAPI.BASE_URL}/divisionsByAddress?address={q}"
    if include_key and api_key:
        url += f"&key={api_key}"
    return url


# Google Civic sandbox election (VIP Test); not real ballot data.
VIP_TEST_ELECTION_ID = "2000"


def is_vip_test_election(election: Dict) -> bool:
    election_id = str(election.get("id") or "").strip()
    name = (election.get("name") or "").strip().lower()
    return election_id == VIP_TEST_ELECTION_ID or "vip test" in name


def filter_civic_elections(elections: List[Dict]) -> List[Dict]:
    """Drop Google's VIP Test Election and any similar sandbox rows."""
    return [e for e in (elections or []) if not is_vip_test_election(e)]


def elections_for_state(elections: List[Dict], state_code: str) -> List[Dict]:
    """
    Filter electionQuery rows to a single state.

    Only ``/state:{xx}`` OCD divisions are included. Bare ``country:us`` rows are
    omitted because Google's only recurring ``country:us`` row is the VIP Test
    sandbox (id 2000), not a real local ballot.
    """
    state = (state_code or "").strip().lower()
    if not state:
        return filter_civic_elections(elections or [])
    out: List[Dict] = []
    for election in filter_civic_elections(elections or []):
        ocd = (election.get("ocdDivisionId") or "").lower()
        if f"/state:{state}" in ocd:
            out.append(election)
    return out


def sanitize_civic_error_message(message: str) -> str:
    """Clean httpx/Google error text for logs and cache JSON (fix typos, redact keys)."""
    text = (message or "").replace("Not Foud", "Not Found")
    text = re.sub(r"([?&]key=)[^&'\s\\]+", r"\1REDACTED", text)
    return text


class GoogleCivicAPI:
    """
    Integration with Google Civic Information API (Elections + Voter Info + Divisions).
    """

    BASE_URL = "https://www.googleapis.com/civicinfo/v2"

    def __init__(self, api_key: Optional[str] = None):
        if api_key:
            self.api_key = api_key
        elif SPARK_AVAILABLE and hasattr(settings, "google_civic_api_key"):
            self.api_key = settings.google_civic_api_key
        else:
            self.api_key = None
            logger.warning("⚠️  GOOGLE_CIVIC_API_KEY not found")
            logger.warning("   Get one at: https://console.cloud.google.com/")
            logger.warning("   Add to .env: GOOGLE_CIVIC_API_KEY=your-key")

        self.cache_dir = Path("data/cache/google_civic")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def get_elections(self) -> Dict:
        """
        elections.electionQuery — master list of elections Google has VIP data for.

        Returns id, name, electionDay, ocdDivisionId for each row.
        """
        if not self.api_key:
            raise ValueError("Google Civic API key required")

        logger.info("Fetching upcoming elections")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/elections",
                    params={"key": self.api_key},
                )
                response.raise_for_status()
                data = response.json()
                elections_data = {
                    "elections": data.get("elections", []),
                    "kind": data.get("kind"),
                    "source": "google_civic_elections",
                    "source_url": civic_elections_url(),
                    "fetched_at": datetime.utcnow().isoformat(),
                }
                logger.info(f"✅ Found {len(elections_data['elections'])} upcoming elections")
                return elections_data
            except httpx.HTTPStatusError as e:
                body = sanitize_civic_error_message(e.response.text or "")
                logger.error(f"HTTP error: {e.response.status_code} - {body}")
                raise
            except Exception as e:
                logger.error(f"Error fetching elections: {sanitize_civic_error_message(str(e))}")
                raise

    async def get_voter_info(
        self,
        address: str,
        election_id: Optional[str] = None,
    ) -> Dict:
        """
        elections.voterInfoQuery — VIP polling places, contests, candidates, referendums.

        ``election_id`` is required when no default upcoming election applies to the address.
        """
        if not self.api_key:
            raise ValueError("Google Civic API key required")

        raw_address = (address or "").strip()
        query_address = normalize_civic_address(raw_address)
        params: Dict[str, str] = {
            "address": query_address,
            "key": self.api_key,
        }
        if election_id:
            params["electionId"] = str(election_id)

        logger.info(
            "Fetching voter info for: %s (electionId=%s)",
            query_address,
            election_id or "default",
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/voterinfo",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                normalized = data.get("normalizedInput") or {}
                voter_info = {
                    **data,
                    "address": query_address,
                    "raw_address": raw_address,
                    "election_id": str(election_id) if election_id else None,
                    "normalized_address": normalized.get("line1") or normalized.get("city") or query_address,
                    "polling_locations": data.get("pollingLocations", []),
                    "early_vote_sites": data.get("earlyVoteSites", []),
                    "drop_off_locations": data.get("dropOffLocations", []),
                    "contests": data.get("contests", []),
                    "state": data.get("state", []),
                    "election": data.get("election"),
                    "source": "google_civic_voterinfo",
                    "source_url": civic_voterinfo_url(query_address, election_id=election_id),
                    "fetched_at": datetime.utcnow().isoformat(),
                }
                n_contests = len(voter_info["contests"])
                n_polling = len(voter_info["polling_locations"])
                logger.info(
                    "✅ Voter info for %s: %d contest(s), %d polling location(s)",
                    query_address,
                    n_contests,
                    n_polling,
                )
                return voter_info
            except httpx.HTTPStatusError as e:
                body = sanitize_civic_error_message(e.response.text or "")
                logger.error(f"HTTP error: {e.response.status_code} - {body}")
                raise httpx.HTTPStatusError(
                    sanitize_civic_error_message(str(e)),
                    request=e.request,
                    response=e.response,
                ) from e
            except Exception as e:
                logger.error(f"Error fetching voter info: {sanitize_civic_error_message(str(e))}")
                raise

    async def get_divisions_by_address(self, address: str) -> Dict:
        """Look up OCD division IDs for a residential address (post-Representatives turndown)."""
        if not self.api_key:
            raise ValueError("Google Civic API key required. Set GOOGLE_CIVIC_API_KEY in .env")

        raw_address = (address or "").strip()
        query_address = normalize_civic_address(raw_address)
        params = {"address": query_address, "key": self.api_key}

        logger.info(f"Fetching divisions for address: {query_address}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/divisionsByAddress",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                return {
                    **data,
                    "address": query_address,
                    "raw_address": raw_address,
                    "source": "google_civic_divisions_by_address",
                    "source_url": civic_divisions_by_address_url(query_address),
                    "fetched_at": datetime.utcnow().isoformat(),
                }
            except httpx.HTTPStatusError as e:
                body = sanitize_civic_error_message(e.response.text or "")
                logger.error(f"HTTP error: {e.response.status_code} - {body}")
                raise httpx.HTTPStatusError(
                    sanitize_civic_error_message(str(e)),
                    request=e.request,
                    response=e.response,
                ) from e
            except Exception as e:
                logger.error(f"Error fetching divisions by address: {sanitize_civic_error_message(str(e))}")
                raise

    def save_to_json(self, data: Dict, filename: str):
        """Save data to JSON cache."""
        import json

        filepath = self.cache_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"💾 Saved to {filepath}")


async def example_usage():
    """Example usage of Google Civic API (Elections + Voter Info)."""
    api = GoogleCivicAPI()

    if not api.api_key:
        logger.error("❌ API key not found. Please set GOOGLE_CIVIC_API_KEY in .env")
        return

    logger.info("\n" + "=" * 80)
    logger.info("Example 1: elections.electionQuery")
    logger.info("=" * 80)

    try:
        elections = await api.get_elections()
        election_rows = elections.get("elections", [])
        print(f"\n✅ Found {len(election_rows)} upcoming elections:")
        for election in election_rows[:10]:
            print(f"\n   • {election.get('name')}")
            print(f"     Date: {election.get('electionDay')}")
            print(f"     ID: {election.get('id')}")
            print(f"     OCD: {election.get('ocdDivisionId')}")
        api.save_to_json(elections, "upcoming_elections.json")
    except Exception as e:
        logger.error(f"Error: {e}")

    logger.info("\n" + "=" * 80)
    logger.info("Example 2: elections.voterInfoQuery")
    logger.info("=" * 80)

    sample_address = "2201 University Blvd, Tuscaloosa, AL 35401"
    try:
        elections = await api.get_elections()
        relevant = elections_for_state(elections.get("elections", []), "AL")
        election_id = str(relevant[0]["id"]) if relevant else None
        voter_info = await api.get_voter_info(sample_address, election_id=election_id)
        election = voter_info.get("election") or {}
        print(f"\n✅ Voter Information:")
        print(f"   Election: {election.get('name', 'N/A')}")
        print(f"   Polling locations: {len(voter_info.get('polling_locations') or [])}")
        print(f"   Early vote sites: {len(voter_info.get('early_vote_sites') or [])}")
        print(f"   Contests: {len(voter_info.get('contests') or [])}")
        api.save_to_json(voter_info, "tuscaloosa_voter_info.json")
    except Exception as e:
        logger.error(f"Error: {e}")

    logger.info("\n✅ Examples complete!")


if __name__ == "__main__":
    asyncio.run(example_usage())
