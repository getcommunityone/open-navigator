"""
Built-in meeting-archive seed URLs for pilot jurisdictions.

Merged at crawl start (like ``jurisdiction_contact_seed_urls``) so Agenda Center / CivicClerk
pages are fetched even when not linked from a shallow homepage crawl.

Disable with ``SCRAPED_MEETINGS_BUILTIN_SEEDS=false``.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

_BUILTIN: Dict[str, Tuple[str, ...]] = {
    "municipality_0155200": (
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
    builtin = () if builtin_off else _BUILTIN.get(jid, ())
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
