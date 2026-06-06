"""
Person-detail endpoint, backed by the MDM person master (public.mdm_person).

Serves a single person by their unique row key (person_uid), which the /search
person results link to (url=/person/{person_uid}).

We deliberately key on person_uid, NOT master_person_id. The MDM resolved-entity
id over-merges badly: a single master_person_id can blob together 50+ unrelated
people in the same city (e.g. one Tuscaloosa, AL id covers Karen Jane Chapman,
John Bowyer, Jon Smith, ...). So master_person_id does not identify the person a
user clicked. person_uid is the table's true unique PK — one row per real source
occurrence — so it resolves to exactly the clicked person. Org affiliations are
scoped to that single person via the bridge (officer_person_uid == source_pk).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from opentelemetry import trace

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/person", tags=["person"])

tracer = trace.get_tracer(__name__)


class PersonOrganization(BaseModel):
    """A single organization affiliation for a person."""
    title: Optional[str] = None
    organization: Optional[str] = None
    master_org_id: Optional[str] = None
    compensation: Optional[float] = None


class PersonColleague(BaseModel):
    """A peer official in the same jurisdiction (government person subtype only).

    Powers the "Other officials in {jurisdiction}" cross-navigation on the detail
    page — each links to that peer's own /person/{person_uid}.
    """
    person_uid: str
    name: str
    title: Optional[str] = None
    photo_url: Optional[str] = None


class PersonDetail(BaseModel):
    """A single person, keyed by their unique person_uid."""
    person_uid: str
    master_person_id: Optional[str] = None
    name: str
    state_code: Optional[str] = None
    city: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    # Official website of the leader's jurisdiction (local leaders only; resolved
    # on the contact_official mart). None for MDM persons and unresolved leaders.
    jurisdiction_website: Optional[str] = None
    # Headshot URL (local leaders, from contact_official.photo_url). None for MDM
    # persons (the master has no photo column) and officials with no headshot.
    photo_url: Optional[str] = None
    # Biography prose (local leaders, from contact_official.biography — sourced
    # from the scraped municipal directory pages, e.g. Northport's CivicPlus
    # detail pages, or the official_photo_override seed for a mayor's "meet the
    # mayor" page). None for MDM persons and officials with no bio.
    biography: Optional[str] = None
    organizations: List[PersonOrganization] = Field(default_factory=list)
    # Peer officials in the same jurisdiction (officials only; empty for MDM
    # persons and for officials with no resolved jurisdiction_id). Drives the
    # "Other officials in {jurisdiction}" cross-navigation.
    colleagues: List[PersonColleague] = Field(default_factory=list)


# Single person row by the true unique PK (person_uid). No DISTINCT ON needed —
# person_uid identifies exactly one row.
_PERSON_SQL = """
    SELECT
        p.person_uid,
        p.master_person_id,
        p.full_name,
        p.email,
        p.phone,
        p.city_norm,
        p.state_code
    FROM mdm_person p
    WHERE p.person_uid = $1
"""

# Org affiliations for THIS single person only. The bridge keys on
# officer_person_uid == mdm_person.source_pk (person_uid is a different,
# double-hashed key), so we join through source_pk for this one person_uid.
# DISTINCT de-dups repeated (title, org, comp) tuples across tax years.
_ORGS_SQL = """
    SELECT DISTINCT
        b.title,
        b.org_name,
        b.master_org_id,
        b.reportable_comp_org
    FROM mdm_person p
    JOIN mdm_bridge_person_organization b
        ON b.officer_person_uid = p.source_pk
    WHERE p.person_uid = $1
    ORDER BY b.reportable_comp_org DESC NULLS LAST, b.org_name
"""

# Fallback lookup for elected/appointed officials, resolved via the person
# SUBTYPE public.person_government. Leader search results (result_type='leader')
# carry an official id (= the OCD membership id, person_government.person_id), not
# an mdm_person person_uid, so /person/{id} resolves them here when the id misses
# mdm_person. The id namespaces are disjoint, so this only fires for genuine
# official ids. The office itself is surfaced as the single org row.
#
# person_government is a deterministic person subtype (one row per official×role,
# keyed by the exact OCD membership id) carrying the government-specific
# attributes mdm_person lacks — office title, jurisdiction, photo, and the
# biography (scraped municipal directory pages, e.g. Northport's CivicPlus detail
# pages, keyed to the EXACT membership row, so always the right person's bio).
#
# biography is read via `to_jsonb(o) ->> 'biography'` (not `o.biography`) as a
# deliberate safety net: if the mart is ever rebuilt from a stale model WITHOUT
# the column, this returns NULL instead of crashing the endpoint with "column
# o.biography does not exist" (the failure mode that previously broke this route).
_OFFICIAL_SQL = """
    SELECT
        o.person_id,
        o.master_person_id,
        o.full_name,
        o.title,
        o.jurisdiction,
        o.office,
        o.email,
        o.phone,
        o.state_code,
        o.website_url,
        o.photo_url,
        o.jurisdiction_id,
        to_jsonb(o) ->> 'biography' AS biography
    FROM person_government o
    WHERE o.person_id = $1
"""

# Peer officials sharing the clicked official's jurisdiction (same jurisdiction_id),
# excluding the official themselves. Backs the "Other officials in {jurisdiction}"
# cross-navigation. jurisdiction_id is indexed on person_government; current
# officials first, then a stable name order. Capped so a large council/legislature
# does not balloon the detail payload.
_COLLEAGUES_SQL = """
    SELECT
        o.person_id,
        o.full_name,
        o.title,
        o.photo_url
    FROM person_government o
    WHERE o.jurisdiction_id = $1
      AND o.person_id <> $2
    ORDER BY o.is_current DESC, o.full_name
    LIMIT 24
"""


def _official_to_detail(row, colleagues: List[PersonColleague]) -> PersonDetail:
    """Map a person_government (official subtype) row onto the shared PersonDetail.

    The official's office (title + jurisdiction/office) is surfaced as the
    single organization entry so the existing detail UI renders it unchanged.
    colleagues are the peer officials in the same jurisdiction (may be empty).
    """
    # Prefer the jurisdiction (e.g. "Tuscaloosa Government") over the coarse
    # office code (e.g. "government") for the org affiliation display.
    affiliation = row["jurisdiction"] or row["office"]
    organizations = [
        PersonOrganization(
            title=row["title"],
            organization=affiliation,
            master_org_id=None,
            compensation=None,
        )
    ]
    return PersonDetail(
        person_uid=row["person_id"],
        master_person_id=row["master_person_id"],
        name=row["full_name"] or "Unknown",
        state_code=row["state_code"],
        city=row["jurisdiction"],
        email=row["email"],
        phone=row["phone"],
        jurisdiction_website=row["website_url"],
        photo_url=row["photo_url"],
        biography=row["biography"],
        organizations=organizations,
        colleagues=colleagues,
    )


@router.get("/{person_uid:path}", response_model=PersonDetail)
async def get_person(person_uid: str) -> PersonDetail:
    """
    Return a single person (and their org affiliations) by person_uid.
    404 if no person row matches.
    """
    with tracer.start_as_current_span("person-detail") as span:
        span.set_attribute("person.person_uid", person_uid)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("person-detail.query-person"):
                    person_row = await conn.fetchrow(_PERSON_SQL, person_uid)

                if person_row is None:
                    # Not in the MDM master — resolve as the government person
                    # subtype (person_government) so leader search results (which
                    # carry an official id, not a person_uid) still drill into a
                    # real detail page.
                    with tracer.start_as_current_span("person-detail.query-official"):
                        official_row = await conn.fetchrow(_OFFICIAL_SQL, person_uid)
                    if official_row is not None:
                        # Peer officials in the same jurisdiction (cross-nav).
                        # Only when the official resolved to a jurisdiction_id.
                        colleagues: List[PersonColleague] = []
                        jurisdiction_id = official_row["jurisdiction_id"]
                        if jurisdiction_id:
                            with tracer.start_as_current_span(
                                "person-detail.query-colleagues"
                            ):
                                colleague_rows = await conn.fetch(
                                    _COLLEAGUES_SQL,
                                    jurisdiction_id,
                                    official_row["person_id"],
                                )
                            colleagues = [
                                PersonColleague(
                                    person_uid=r["person_id"],
                                    name=r["full_name"] or "Unknown",
                                    title=r["title"],
                                    photo_url=r["photo_url"],
                                )
                                for r in colleague_rows
                            ]
                        span.set_attribute("person.found", True)
                        span.set_attribute("person.source", "person_government")
                        span.set_attribute("person.colleague_count", len(colleagues))
                        return _official_to_detail(official_row, colleagues)

                    span.set_attribute("person.found", False)
                    raise HTTPException(
                        status_code=404,
                        detail=f"No person found for person_uid '{person_uid}'",
                    )
                span.set_attribute("person.found", True)
                span.set_attribute("person.source", "mdm_person")

                with tracer.start_as_current_span("person-detail.query-orgs"):
                    org_rows = await conn.fetch(_ORGS_SQL, person_uid)

            organizations = [
                PersonOrganization(
                    title=row["title"],
                    organization=row["org_name"],
                    master_org_id=row["master_org_id"],
                    compensation=(
                        float(row["reportable_comp_org"])
                        if row["reportable_comp_org"] is not None
                        else None
                    ),
                )
                for row in org_rows
            ]
            span.set_attribute("person.org_count", len(organizations))

            logger.info(
                "👤 Person detail {} -> {} org(s)",
                person_uid,
                len(organizations),
            )

            return PersonDetail(
                person_uid=person_row["person_uid"],
                master_person_id=person_row["master_person_id"],
                name=person_row["full_name"] or "Unknown",
                state_code=person_row["state_code"],
                city=person_row["city_norm"],
                email=person_row["email"],
                phone=person_row["phone"],
                organizations=organizations,
            )

        except HTTPException:
            raise
        except Exception as e:
            span.record_exception(e)
            logger.error("Person detail error for {}: {}", person_uid, e)
            raise HTTPException(status_code=500, detail="Failed to load person detail")
