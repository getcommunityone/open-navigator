"""
Built-in meeting-archive seed URLs for pilot jurisdictions.

Merged at crawl start (like ``jurisdiction_contact_seed_urls``) so Agenda Center / CivicClerk
pages are fetched even when not linked from a shallow homepage crawl.

Disable with ``SCRAPED_MEETINGS_BUILTIN_SEEDS=false``.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

from scripts.jurisdictions.jurisdiction_id import builtin_seed_urls_for_jurisdiction

_BUILTIN: Dict[str, Tuple[str, ...]] = {
    # Baker County, GA — Wix minutes/agendas table + ``/_files/ugd/*.pdf`` (labels in aria-label).
    "baker_13007": (
        "https://www.bakercountyga.com/minutes-and-agendas",
    ),
    # Ben Hill County, GA — WordPress commissioner meetings tables (agenda/minutes PDFs).
    "ben_hill_13017": (
        "https://www.benhillcounty-ga.gov/county-commissioner-meetings/",
    ),
    # Barrow County, GA — CivicPlus board meeting videos (Vimeo links on Quick Links hub).
    "barrow_13013": (
        "https://www.barrowga.org/390/Watch-a-Board-Meeting-Video",
    ),
    # Gwinnett County, GA — TV Gwinnett commission meetings (ChampDS embed)
    "gwinnett_13135": (
        "https://www.gwinnettcounty.com/government/departments/communications/"
        "tv-gwinnett/videos/commission-meetings",
    ),
    # Shelby County, AL — CivicPlus Agenda Center + calendar
    "shelby_01117": (
        "https://www.shelbyal.com/AgendaCenter",
        "https://www.shelbyal.com/AgendaCenter/County-Commission-1",
        "https://www.shelbyal.com/calendar.aspx",
    ),
    # City of Northport, AL — CivicPlus Agenda Center
    "northport_0155200": (
        "https://www.northportal.gov/129/Agendas-Minutes",
        "https://www.northportal.gov/AgendaCenter",
        "https://www.northportal.gov/calendar.aspx",
    ),
}


def merged_meeting_seed_urls(
    jurisdiction_id: str,
    cli_seeds: Optional[Sequence[str]],
) -> List[str]:
    v = (os.getenv("SCRAPED_MEETINGS_BUILTIN_SEEDS") or "true").strip().lower()
    builtin_off = v in ("0", "false", "no", "off")
    jid = (jurisdiction_id or "").strip()
    builtin = () if builtin_off else builtin_seed_urls_for_jurisdiction(jid, _BUILTIN)
    cli = tuple(str(x).strip() for x in (cli_seeds or []) if str(x).strip())
    ordered = list(builtin) + list(cli)
    out: List[str] = []
    seen: set[str] = set()
    for u in ordered:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out
