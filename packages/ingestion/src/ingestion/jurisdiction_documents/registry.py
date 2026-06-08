"""Curated registry of jurisdiction-grain civic documents.

Jurisdiction-grain documents are standing publications that belong to a
JURISDICTION rather than a single meeting: comprehensive plans / frameworks,
unified development / zoning ordinances, ordinance codes, and zoning maps. They
have no meeting date, so they cannot be linked through ``event_meeting_document``
(which matches a doc to a meeting on jurisdiction + date + body). Instead they
link directly to the owning jurisdiction, and to civic data (decisions, bills)
through the ordinance numbers they contain.

NO FABRICATED DATA (CLAUDE.md): every entry here must be a REAL, publicly
published document with a real URL and a real owning ``jurisdiction_id`` that
exists in ``public.jurisdictions``. Leave ``adopted_date`` ``None`` unless the
adoption date is known for certain — an unverified date is worse than no date.

This is a curated registry rather than a scrape: these flagship documents are
few, authoritative, and rarely change. A discovery scraper can append to the
same ``bronze.bronze_jurisdiction_document`` table later without changing the
downstream dbt contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

# Allowed jurisdiction-grain document types. Keep in sync with the
# `document_type` accepted-values test in
# dbt_project/models/marts/_schema_jurisdiction_document.yml.
DOCUMENT_TYPES: tuple[str, ...] = (
    "comprehensive_plan",   # a city/county comprehensive / framework plan
    "zoning_ordinance",     # unified development / zoning ordinance code
    "ordinance_code",       # the municipal code of ordinances
    "zoning_map",           # official zoning / future-land-use map
)


@dataclass(frozen=True)
class JurisdictionDocument:
    """One real jurisdiction-grain document (before any DB shaping)."""

    jurisdiction_id: str            # FK -> public.jurisdictions.jurisdiction_id
    document_type: str              # one of DOCUMENT_TYPES
    title: str
    document_url: str
    source: str                     # publishing site / origin
    adopted_date: Optional[date] = None  # None unless verified


# --- The real registry -------------------------------------------------------
# Tuscaloosa "Framework": the City of Tuscaloosa's comprehensive plan, published
# complete with the adopting ordinance and zoning maps. Owner is the CITY
# (tuscaloosa_0177256), NOT the county (tuscaloosa_01125) — a distinction the
# meeting-document enrichment path got wrong because both share a FIPS bucket.
# adopted_date left None: the filename says "FOR DECEMBER 17" and it sits under a
# 2024/11 upload path, but the actual adoption date is not verified here.
REGISTRY: tuple[JurisdictionDocument, ...] = (
    JurisdictionDocument(
        jurisdiction_id="tuscaloosa_0177256",
        document_type="comprehensive_plan",
        title=(
            "Framework — City of Tuscaloosa Comprehensive Plan "
            "(complete with ordinance and maps)"
        ),
        document_url=(
            "https://framework.tuscaloosa.com/wp-content/uploads/2024/11/"
            "FRAMEWORK-COMPLETE-WITH-ORDINANCE-AND-MAPS-FOR-DECEMBER-17.pdf"
        ),
        source="framework.tuscaloosa.com",
        adopted_date=None,
    ),
)
