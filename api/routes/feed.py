"""
Feed-personalization API: a user's saved locations, lenses, and signals.

Backs the /feed-setup screen. Reads/writes three operational ORM tables
(user_locations / user_lens_prefs / user_signal_prefs — see api/models.py),
keyed to the authenticated user. NO transformation/SQL logic lives here beyond
straight ORM CRUD; these are operational user-preference tables, not dbt marts.

Endpoints:
  - GET  /api/feed/config   (auth)    -> assembled config for the current user
  - PUT  /api/feed/config   (auth)    -> full-replace the config in one txn
  - GET  /api/feed/places   (no auth) -> place typeahead (Nominatim proxy reuse)

Lens/signal slugs are validated against server-side allow-sets so junk can't be
stored. Place results carry only real geocoder hits — no fabricated/placeholder
data (CLAUDE.md).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import User, UserLocation, UserLensPref, UserSignalPref
from api.routes.geocode import _throttled_get

router = APIRouter(prefix="/feed", tags=["feed"])

tracer = trace.get_tracer(__name__)


# ---------------------------------------------------------------------------
# Server-side allow-sets. Labels/copy live in the frontend; only slugs here.
# ---------------------------------------------------------------------------
ALLOWED_LENSES = frozenset({
    "family-first",
    "faith-community",
    "charitable-impact",
    "neighborhood-life",
    "education",
    "local-economy",
})

ALLOWED_SIGNALS = frozenset({
    "contested",
    "money-moves",
    "raised-eyebrows",
    "moving-fast",
    "slipped-through",
    "helping-hands",
    "watch-next",
})

ALLOWED_SHARED_LEVELS = frozenset({"street", "district", "city", "county", "state"})


# ---------------------------------------------------------------------------
# Pydantic models (inline, mirroring lenses.py convention).
# ---------------------------------------------------------------------------
class LocationIn(BaseModel):
    """A location as submitted on save (resolved geo all optional)."""
    name: str
    shared_level: str = "city"
    is_primary: bool = False
    state_code: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    place_fips: Optional[str] = None
    county_fips: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    jurisdiction_id: Optional[str] = None

    @field_validator("shared_level")
    @classmethod
    def _check_shared_level(cls, v: str) -> str:
        if v not in ALLOWED_SHARED_LEVELS:
            raise ValueError(
                f"shared_level must be one of {sorted(ALLOWED_SHARED_LEVELS)} (got '{v}')"
            )
        return v


class LocationOut(BaseModel):
    """A saved location as returned to the client."""
    id: int
    name: str
    shared_level: str
    is_primary: bool
    state_code: Optional[str] = None
    state: Optional[str] = None
    county: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    jurisdiction_id: Optional[str] = None


class FeedConfigIn(BaseModel):
    """Full feed config submitted on save (full replace)."""
    locations: List[LocationIn] = []
    lenses: List[str] = []
    signals: List[str] = []

    @field_validator("lenses")
    @classmethod
    def _check_lenses(cls, v: List[str]) -> List[str]:
        unknown = [s for s in v if s not in ALLOWED_LENSES]
        if unknown:
            raise ValueError(f"unknown lens slug(s): {unknown}")
        # De-dupe while preserving order.
        return list(dict.fromkeys(v))

    @field_validator("signals")
    @classmethod
    def _check_signals(cls, v: List[str]) -> List[str]:
        unknown = [s for s in v if s not in ALLOWED_SIGNALS]
        if unknown:
            raise ValueError(f"unknown signal slug(s): {unknown}")
        return list(dict.fromkeys(v))


class FeedConfigOut(BaseModel):
    """Assembled feed config returned by GET/PUT."""
    locations: List[LocationOut]
    lenses: List[str]
    signals: List[str]
    profile_completed: bool


class PlaceHit(BaseModel):
    """One real geocoder hit for the place typeahead."""
    name: str
    city: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    latitude: float
    longitude: float


class PlacesResponse(BaseModel):
    results: List[PlaceHit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_user(user: Optional[User]) -> User:
    """get_current_user returns Optional[User]; enforce auth here."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _assemble_config(db: Session, user: User) -> FeedConfigOut:
    """Read the three preference tables and shape the config response."""
    locations = (
        db.query(UserLocation)
        .filter(UserLocation.user_id == user.user_id)
        .order_by(UserLocation.is_primary.desc(), UserLocation.id.asc())
        .all()
    )
    lenses = (
        db.query(UserLensPref.lens_slug)
        .filter(UserLensPref.user_id == user.user_id)
        .order_by(UserLensPref.lens_slug.asc())
        .all()
    )
    signals = (
        db.query(UserSignalPref.signal_slug)
        .filter(UserSignalPref.user_id == user.user_id)
        .order_by(UserSignalPref.signal_slug.asc())
        .all()
    )
    return FeedConfigOut(
        locations=[
            LocationOut(
                id=loc.id,
                name=loc.name,
                shared_level=loc.shared_level,
                is_primary=bool(loc.is_primary),
                state_code=loc.state_code,
                state=loc.state,
                county=loc.county,
                latitude=loc.latitude,
                longitude=loc.longitude,
                jurisdiction_id=loc.jurisdiction_id,
            )
            for loc in locations
        ],
        lenses=[row[0] for row in lenses],
        signals=[row[0] for row in signals],
        profile_completed=bool(user.profile_completed),
    )


# 2-letter -> full state name, for syncing the primary location into
# User.state when only a state_code came back from the geocoder.
_STATE_CODE_TO_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/config", response_model=FeedConfigOut)
def get_feed_config(
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedConfigOut:
    """Return the current user's saved feed config (locations/lenses/signals)."""
    user = _require_user(user)
    with tracer.start_as_current_span("feed.get_config") as span:
        span.set_attribute("feed.user_id", user.user_id)
        return _assemble_config(db, user)


@router.put("/config", response_model=FeedConfigOut)
def put_feed_config(
    body: FeedConfigIn,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedConfigOut:
    """Full-replace the current user's feed config in a single transaction.

    Deletes all existing rows for the user across the three tables, inserts the
    submitted ones, marks the profile complete, and syncs the primary location's
    city/county/state back into User.city/county/state so Profile.tsx keeps
    rendering the "city, state" header.
    """
    user = _require_user(user)

    with tracer.start_as_current_span("feed.put_config") as span:
        span.set_attribute("feed.user_id", user.user_id)
        span.set_attribute("feed.locations", len(body.locations))
        span.set_attribute("feed.lenses", len(body.lenses))
        span.set_attribute("feed.signals", len(body.signals))

        try:
            # Full replace: clear the user's existing rows in all three tables.
            db.query(UserLocation).filter(UserLocation.user_id == user.user_id).delete(
                synchronize_session=False
            )
            db.query(UserLensPref).filter(UserLensPref.user_id == user.user_id).delete(
                synchronize_session=False
            )
            db.query(UserSignalPref).filter(UserSignalPref.user_id == user.user_id).delete(
                synchronize_session=False
            )

            # If nothing is flagged primary, treat the first location as primary.
            has_primary = any(loc.is_primary for loc in body.locations)
            primary_loc: Optional[LocationIn] = None
            for idx, loc in enumerate(body.locations):
                is_primary = loc.is_primary or (not has_primary and idx == 0)
                if is_primary and primary_loc is None:
                    primary_loc = loc
                db.add(UserLocation(
                    user_id=user.user_id,
                    name=loc.name,
                    shared_level=loc.shared_level,
                    is_primary=is_primary,
                    state_code=loc.state_code,
                    state=loc.state,
                    county=loc.county,
                    place_fips=loc.place_fips,
                    county_fips=loc.county_fips,
                    latitude=loc.latitude,
                    longitude=loc.longitude,
                    jurisdiction_id=loc.jurisdiction_id,
                ))

            for slug in body.lenses:
                db.add(UserLensPref(user_id=user.user_id, lens_slug=slug))
            for slug in body.signals:
                db.add(UserSignalPref(user_id=user.user_id, signal_slug=slug))

            # Sync the primary location into the existing User.* columns so the
            # legacy Profile.tsx "city, state" header keeps working.
            if primary_loc is not None:
                resolved_state = primary_loc.state
                if not resolved_state and primary_loc.state_code:
                    resolved_state = _STATE_CODE_TO_NAME.get(
                        primary_loc.state_code.upper(), primary_loc.state_code
                    )
                user.county = primary_loc.county
                user.state = resolved_state
                # The primary's "city" — prefer an explicit city-ish name. The
                # location `name` is the display label (e.g. "Tuscaloosa, AL");
                # strip a trailing ", ST" so the header reads cleanly.
                city = primary_loc.name
                if primary_loc.state_code and city.endswith(f", {primary_loc.state_code}"):
                    city = city[: -len(f", {primary_loc.state_code}")]
                user.city = city.strip() or None

            user.profile_completed = True

            db.commit()
        except Exception as exc:  # noqa: BLE001 — roll back, surface a clean 500
            db.rollback()
            span.record_exception(exc)
            logger.error("Feed config save failed for user {}: {}", user.user_id, exc)
            raise HTTPException(status_code=500, detail="Failed to save feed config")

        db.refresh(user)
        return _assemble_config(db, user)


def _derive_state_code(address: dict) -> Optional[str]:
    """Pull a 2-letter state code from a Nominatim address block.

    Prefers ISO3166-2-lvl4 ("US-AL" -> "AL"); falls back to a bare `state` only
    when it is already a 2-letter code (never invents one).
    """
    iso = address.get("ISO3166-2-lvl4")
    if iso and "-" in iso:
        code = iso.split("-", 1)[1].strip().upper()
        if len(code) == 2:
            return code
    state = address.get("state")
    if isinstance(state, str) and len(state) == 2:
        return state.upper()
    return None


@router.get("/places", response_model=PlacesResponse)
async def feed_places(
    q: str = Query("", description="Free-text place query (min 3 chars)."),
) -> PlacesResponse:
    """Place typeahead backed by the Nominatim proxy — real hits only.

    Maps each geocoder result to a clean {name, city, county, state,
    state_code, latitude, longitude}. Short/empty queries (<3 chars) return an
    empty result set; no fabricated/placeholder suggestions (CLAUDE.md).
    """
    query = (q or "").strip()
    if len(query) < 3:
        return PlacesResponse(results=[])

    with tracer.start_as_current_span("feed.places") as span:
        span.set_attribute("feed.places.q_len", len(query))
        try:
            # Reuse the geocode proxy's throttled+cached Nominatim call directly
            # (geocode_search enforces min_length=3 at the param layer, which we
            # already handle above).
            payload = await _throttled_get(
                "/search",
                {
                    "q": query,
                    "format": "json",
                    "addressdetails": "1",
                    "countrycodes": "us",
                    "limit": "6",
                },
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            logger.error("Place typeahead failed for '{}': {}", query, exc)
            raise HTTPException(status_code=502, detail="Geocoder error.")

        results: List[PlaceHit] = []
        for item in payload or []:
            address = item.get("address") or {}
            city = (
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("hamlet")
                or address.get("municipality")
            )
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue  # no usable coordinates -> skip (no fabricated geo)
            results.append(PlaceHit(
                name=item.get("display_name") or city or query,
                city=city,
                county=address.get("county"),
                state=address.get("state"),
                state_code=_derive_state_code(address),
                latitude=lat,
                longitude=lon,
            ))

        span.set_attribute("feed.places.hits", len(results))
        return PlacesResponse(results=results)
