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
    organizations: List[PersonOrganization] = Field(default_factory=list)


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

# Fallback lookup for elected/appointed officials. Leader search results
# (result_type='leader') come from contact_official — a separate table with no
# person_uid linkage to the MDM master — so /person/{id} resolves them here when
# the id misses mdm_person. The id namespaces are disjoint, so this only fires
# for genuine official ids. The office itself is surfaced as the single org row.
_OFFICIAL_SQL = """
    SELECT
        o.id,
        o.full_name,
        o.title,
        o.jurisdiction,
        o.office,
        o.email,
        o.phone,
        o.state_code,
        o.website_url
    FROM contact_official o
    WHERE o.id = $1
"""


def _official_to_detail(row) -> PersonDetail:
    """Map a contact_official row onto the shared PersonDetail shape.

    The official's office (title + jurisdiction/office) is surfaced as the
    single organization entry so the existing detail UI renders it unchanged.
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
        person_uid=row["id"],
        master_person_id=None,
        name=row["full_name"] or "Unknown",
        state_code=row["state_code"],
        city=row["jurisdiction"],
        email=row["email"],
        phone=row["phone"],
        jurisdiction_website=row["website_url"],
        organizations=organizations,
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
                    # Not in the MDM master — fall back to contact_official so
                    # leader search results (which carry an official id, not a
                    # person_uid) still drill into a real detail page.
                    with tracer.start_as_current_span("person-detail.query-official"):
                        official_row = await conn.fetchrow(_OFFICIAL_SQL, person_uid)
                    if official_row is not None:
                        span.set_attribute("person.found", True)
                        span.set_attribute("person.source", "contact_official")
                        return _official_to_detail(official_row)

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
