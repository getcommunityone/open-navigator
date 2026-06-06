"""US Census Bureau batch geocoder client (free, no API key).

Endpoint: ``https://geocoding.geo.census.gov/geocoder/locations/addressbatch``
with ``benchmark=Public_AR_Current`` and ``returntype=locations``. A CSV of up
to 10,000 rows (``id,street,city,state,zip``) is POSTed as a multipart file; the
service returns a CSV with one row per input id.

Returned CSV columns (no header):
    id, input_address, match_status, match_type, matched_address,
    "longitude,latitude", tigerline_id, side

Note the coordinate field is ``lon,lat`` (longitude FIRST), which we split into
separate floats. ``match_status`` is ``Match`` / ``No_Match`` / ``Tie``.
"""

from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass

from loguru import logger

CENSUS_BATCH_URL = (
    "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
)
BENCHMARK = "Public_AR_Current"
RETURNTYPE = "locations"
# Census documents a 10,000-record-per-request ceiling.
MAX_BATCH = 10_000
USER_AGENT = "OpenNavigator-PolicyAnalysis/1.0 (civic-meeting-research)"


@dataclass(frozen=True)
class CensusGeocodeResult:
    """One parsed result row from the Census batch geocoder."""

    record_id: str
    matched: bool
    latitude: float | None
    longitude: float | None
    matched_address: str | None


@dataclass(frozen=True)
class CensusAddress:
    """One input address keyed by an opaque record id."""

    record_id: str
    street: str
    city: str = ""
    state: str = ""
    zip_code: str = ""


def build_census_csv(addresses: list[CensusAddress]) -> str:
    """Serialize addresses to the headerless ``id,street,city,state,zip`` CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for addr in addresses:
        writer.writerow(
            [
                addr.record_id,
                addr.street,
                addr.city,
                addr.state,
                addr.zip_code,
            ]
        )
    return buf.getvalue()


def _parse_coord(raw: str) -> tuple[float | None, float | None]:
    """Parse the Census ``lon,lat`` coordinate field into ``(lat, lon)``."""
    raw = (raw or "").strip()
    if "," not in raw:
        return None, None
    lon_s, lat_s = raw.split(",", 1)
    try:
        return float(lat_s), float(lon_s)
    except ValueError:
        return None, None


def parse_census_csv(body: str) -> list[CensusGeocodeResult]:
    """Parse the Census batch-geocoder response CSV into result rows.

    Resilient to quoting and to the variable column count of ``No_Match`` rows
    (which omit the matched-address / coordinate / tigerline columns).
    """
    results: list[CensusGeocodeResult] = []
    reader = csv.reader(io.StringIO(body))
    for row in reader:
        if not row:
            continue
        record_id = (row[0] or "").strip()
        if not record_id:
            continue
        status = (row[2].strip() if len(row) > 2 else "").lower()
        matched = status == "match"
        lat: float | None = None
        lon: float | None = None
        matched_address: str | None = None
        if matched and len(row) >= 6:
            matched_address = (row[4] or "").strip() or None
            lat, lon = _parse_coord(row[5])
            if lat is None or lon is None:
                matched = False
        results.append(
            CensusGeocodeResult(
                record_id=record_id,
                matched=matched,
                latitude=lat,
                longitude=lon,
                matched_address=matched_address,
            )
        )
    return results


class CensusBatchGeocoder:
    """Thin client over the Census batch addressbatch endpoint."""

    def __init__(
        self,
        *,
        url: str = CENSUS_BATCH_URL,
        timeout: float = 180.0,
        max_batch: int = MAX_BATCH,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.max_batch = max_batch

    def geocode_batch(
        self, addresses: list[CensusAddress]
    ) -> list[CensusGeocodeResult]:
        """Geocode up to ``max_batch`` addresses in a single POST."""
        if not addresses:
            return []
        if len(addresses) > self.max_batch:
            raise ValueError(
                f"Census batch limited to {self.max_batch}; got {len(addresses)}"
            )
        csv_body = build_census_csv(addresses)
        body, content_type = _multipart_encode(csv_body)
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": content_type, "User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        return parse_census_csv(text)


def _multipart_encode(csv_body: str) -> tuple[bytes, str]:
    """Encode the addressbatch multipart/form-data body (stdlib only)."""
    boundary = uuid.uuid4().hex
    crlf = "\r\n"
    parts: list[str] = []
    parts.append(f"--{boundary}")
    parts.append(
        'Content-Disposition: form-data; name="addressFile"; '
        'filename="addresses.csv"'
    )
    parts.append("Content-Type: text/csv")
    parts.append("")
    parts.append(csv_body)
    for field, value in (("benchmark", BENCHMARK), ("returntype", RETURNTYPE)):
        parts.append(f"--{boundary}")
        parts.append(f'Content-Disposition: form-data; name="{field}"')
        parts.append("")
        parts.append(value)
    parts.append(f"--{boundary}--")
    parts.append("")
    return crlf.join(parts).encode("utf-8"), (
        f"multipart/form-data; boundary={boundary}"
    )
