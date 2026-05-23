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
        "https://www.tuscco.com/county-officials/county-commission/",
        "https://www.tuscco.com/county-officials/",
        "https://www.tuscco.com/commission-agenda-minutes/",
    ),
    # City of Northport, AL — CivicPlus council directory (northportal.gov)
    "municipality_0155200": (
        "https://www.northportal.gov/220/City-Council",
    ),
    # Bacon County, GA — commissioners roster lives on Administration page, not the homepage.
    "county_13005": (
        "https://baconcounty.org/administration.php",
    ),
    # Bulloch County, GA — commissioners roster page is the top-priority contact target.
    "county_13031": (
        "https://bullochcounty.net/commissioners/",
    ),
    # --- Massachusetts pilot (10 jurisdictions) ---
    # Mayor URLs come first so single-bio mayor pages get crawled before the larger
    # council roster; council URLs follow. See ``scripts/datasources/ma_pilot``.
    # Boston, MA — strong-mayor city; mayor's office on a distinct page.
    "municipality_2507000": (
        "https://www.boston.gov/departments/mayors-office",
        "https://www.boston.gov/departments/city-council",
    ),
    # Cambridge, MA — council-manager; mayor is elected from council but has own page.
    "municipality_2511000": (
        "https://www.cambridgema.gov/Departments/mayorsoffice",
        "https://www.cambridgema.gov/citycouncil",
        "https://www.cambridgema.gov/Departments/citycouncil/members",
    ),
    # Worcester, MA — council-manager; mayor is council member at-large.
    "municipality_2582000": (
        "https://www.worcesterma.gov/mayor",
        "https://www.worcesterma.gov/city-council",
        "https://www.worcesterma.gov/city-council/councilors",
    ),
    # Springfield, MA — strong-mayor; legacy CMS path.
    "municipality_2567000": (
        "https://www.springfield-ma.gov/cos/mayor0/",
        "https://www.springfield-ma.gov/cos/council",
    ),
    # Lowell, MA — Plan E (council-manager); mayor elected from council. CivicPlus
    # /CivicEngage staff directory uses h-card markup.
    "municipality_2537000": (
        "https://www.lowellma.gov/533/Meet-the-City-Council",
        "https://www.lowellma.gov/directory.aspx?did=16",
    ),
    # Somerville, MA — strong-mayor.
    "municipality_2562535": (
        "https://www.somervillema.gov/mayor",
        "https://www.somervillema.gov/departments/city-council",
    ),
    # Newton, MA — strong-mayor. Mayor changed Jan 2026 (Fuller -> Laredo); slug may
    # rotate. Multiple candidates so a single 404 doesn't black-hole the mayor row.
    "municipality_2545560": (
        "https://www.newtonma.gov/government/mayor",
        "https://www.newtonma.gov/government/mayor-laredo",
        "https://www.newtonma.gov/government/city-council",
    ),
    # Quincy, MA — strong-mayor (Plan A). Mayor's office under elected_officials/.
    "municipality_2555745": (
        "https://www.quincyma.gov/government/elected_officials/mayor_s_office/index.php",
        "https://www.quincyma.gov/contact_us/mayors_office.php",
        "https://www.quincyma.gov/government/elected_officials/city_council/index.php",
    ),
    # Plymouth County, MA — one of the few still-functioning MA county governments.
    "county_25023": (
        "https://www.plymouthcountyma.gov/222/Commissioners",
        "https://www.plymouthcountyma.gov/directory.aspx?did=12",
    ),
    # Norfolk County, MA — county commissioners site (legacy http, not https).
    "county_25021": (
        "http://www.norfolkcounty.org/county_commission/commissioners.php",
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
