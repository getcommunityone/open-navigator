"""
Built-in contact / directory page seeds for pilot jurisdictions.

Some official bios live on a different host than ``int_jurisdiction_websites`` (e.g. Sweet Grass
County commissioners on ``sgcountymt.gov`` while NACO lists ``sweetgrasscountygov.com``). Seeds are
merged with ``--contact-seed-urls`` and enqueued at crawl start.

Disable with ``SCRAPED_CONTACT_BUILTIN_SEEDS=false``.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

# jurisdiction_id -> absolute URLs (deduped, defaults listed before CLI seeds in merge)
_BUILTIN: Dict[str, Tuple[str, ...]] = {
    # Sweet Grass County, MT — commissioner bios (county site; not always linked from NACO host)
    "county_30097": (
        "https://sgcountymt.gov/government-departments/county-govt/county-commissioners/commissioner-bios/",
    ),
    # City of Big Timber, MT — mayor & council directory / agendas hub
    "municipality_3006475": (
        "https://cityofbigtimber.com/major-council",
    ),
    # Tuscaloosa County, AL — commission / probate directory (WordPress; plain-text emails)
    "county_01125": (
        "https://www.tuscco.com/county-officials/",
        "https://www.tuscco.com/commission-agenda-minutes/",
    ),
}


def merged_contact_seed_urls(
    jurisdiction_id: str,
    cli_seeds: Optional[Sequence[str]],
) -> List[str]:
    """
    Return built-in seeds for ``jurisdiction_id`` (when enabled), then CLI seeds, preserving order
    and dropping duplicates (first wins).
    """
    v = (os.getenv("SCRAPED_CONTACT_BUILTIN_SEEDS") or "true").strip().lower()
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
