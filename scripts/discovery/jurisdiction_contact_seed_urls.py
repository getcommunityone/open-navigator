"""
Built-in contact / directory page seeds for pilot jurisdictions.

Some official bios live on a different host than ``int_jurisdiction_websites`` (e.g. Sweet Grass
County commissioners on ``sgcountymt.gov`` while NACO lists ``sweetgrasscountygov.com``). Seeds are
merged with ``--contact-seed-urls`` and enqueued at crawl start.

Keys use canonical ``{place_slug}_{geoid}`` ids; ``builtin_seed_urls_for_jurisdiction`` also
matches legacy ``county_*`` / ``municipality_*`` keys by GEOID.

Disable with ``SCRAPED_CONTACT_BUILTIN_SEEDS=false``.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

from core_lib.jurisdictions.jurisdiction_id import builtin_seed_urls_for_jurisdiction

# jurisdiction_id -> absolute URLs (deduped, defaults listed before CLI seeds in merge)
_BUILTIN: Dict[str, Tuple[str, ...]] = {
    # Sweet Grass County, MT — commissioner bios (county site; not always linked from NACO host)
    "sweet_grass_30097": (
        "https://sgcountymt.gov/government-departments/county-govt/county-commissioners/commissioner-bios/",
    ),
    # City of Big Timber, MT — mayor & council directory / agendas hub
    "big_timber_3006475": (
        "https://cityofbigtimber.com/major-council",
    ),
    # Shelby County, AL — CivicPlus commission roster + Agenda Center
    "shelby_01117": (
        "https://www.shelbyal.com/93/County-Commission",
        "https://www.shelbyal.com/27/Elected-Officials",
        "https://www.shelbyal.com/185/Municipalities",
    ),
    # Tuscaloosa County, AL — commission / probate directory (WordPress; plain-text emails)
    "tuscaloosa_01125": (
        "https://www.tuscco.com/county-officials/county-commission/",
        "https://www.tuscco.com/county-officials/",
        "https://www.tuscco.com/commission-agenda-minutes/",
    ),
    # City of Northport, AL — CivicPlus council directory (northportal.gov)
    "northport_0155200": (
        "https://www.northportal.gov/220/City-Council",
    ),
    # Bacon County, GA — commissioners roster lives on Administration page, not the homepage.
    "bacon_13005": (
        "https://baconcounty.org/administration.php",
    ),
    # Bulloch County, GA — commissioners roster page is the top-priority contact target.
    "bulloch_13031": (
        "https://bullochcounty.net/commissioners/",
    ),
    # Bibb County, AL — Centreville Tech roster (background-image headshots, shared mailto).
    "bibb_01007": (
        "https://bibbal.com/the-county-commission/",
    ),
    # Choctaw County, AL — WordPress wp-caption commissioner portraits.
    "choctaw_01023": (
        "https://www.choctawcountyal.org/board-of-commissioners/",
    ),
    # Atkinson County, GA — Fusion h3 name + p role on board-of-commissioners page.
    "atkinson_13003": (
        "https://atkinsoncounty.org/board-of-commissioners/",
    ),
    # Dale County, AL — Divi ``et_pb_team_member`` commissioner roster.
    "dale_01045": (
        "https://dalecountyal.org/county-commision/dale-county-alabama-county-commission-commissioners/",
    ),
    # City of Trussville, AL — Infomedia ``<p>`` council / mayor bios (trussville.org).
    "trussville_0176944": (
        "https://trussville.org/government/city-council/",
        "https://trussville.org/government/mayors-office/",
    ),
    # City of Abbeville, AL — Hostinger Zyro ``h6`` + ``p`` elected-officials grid.
    "abbeville_0100124": (
        "https://cityofabbeville.org/elected-officials",
    ),
    # City of Alabaster, AL — CivicPlus council table + ``directory.aspx?EID=`` bios.
    "alabaster_0100820": (
        "https://www.cityofalabaster.com/161/City-Council",
        "https://www.cityofalabaster.com/Directory.aspx?EID=80",
        "https://www.cityofalabaster.com/Directory.aspx?EID=79",
        "https://www.cityofalabaster.com/Directory.aspx?EID=254",
        "https://www.cityofalabaster.com/Directory.aspx?EID=215",
        "https://www.cityofalabaster.com/Directory.aspx?EID=81",
        "https://www.cityofalabaster.com/Directory.aspx?EID=255",
        "https://www.cityofalabaster.com/Directory.aspx?EID=8",
    ),
    # City of Gulf Shores, AL — CivicPlus mayor/council roster + ``directory.aspx?eid=`` bios.
    "gulf_shores_0132272": (
        "https://gulfshoresal.gov/400/Mayor-Council",
        "https://www.gulfshoresal.gov/directory.aspx?eid=195",
        "https://www.gulfshoresal.gov/Directory.aspx?EID=4",
        "https://www.gulfshoresal.gov/Directory.aspx?EID=5",
        "https://www.gulfshoresal.gov/Directory.aspx?EID=6",
    ),
    # --- Massachusetts pilot (10 jurisdictions) ---
    # Mayor URLs come first so single-bio mayor pages get crawled before the larger
    # council roster; council URLs follow. See ``scripts/datasources/ma_pilot``.
    "boston_2507000": (
        "https://www.boston.gov/departments/mayors-office",
        "https://www.boston.gov/departments/city-council",
    ),
    "cambridge_2511000": (
        "https://www.cambridgema.gov/Departments/mayorsoffice",
        "https://www.cambridgema.gov/citycouncil",
        "https://www.cambridgema.gov/Departments/citycouncil/members",
    ),
    "worcester_2582000": (
        "https://www.worcesterma.gov/mayor",
        "https://www.worcesterma.gov/city-council",
        "https://www.worcesterma.gov/city-council/councilors",
    ),
    "springfield_2567000": (
        "https://www.springfield-ma.gov/cos/mayor0/",
        "https://www.springfield-ma.gov/cos/council",
    ),
    "lowell_2537000": (
        "https://www.lowellma.gov/533/Meet-the-City-Council",
        "https://www.lowellma.gov/directory.aspx?did=16",
    ),
    "somerville_2562535": (
        "https://www.somervillema.gov/mayor",
        "https://www.somervillema.gov/departments/city-council",
    ),
    "newton_2545560": (
        "https://www.newtonma.gov/government/mayor",
        "https://www.newtonma.gov/government/mayor-laredo",
        "https://www.newtonma.gov/government/city-council",
    ),
    "quincy_2555745": (
        "https://www.quincyma.gov/government/elected_officials/mayor_s_office/index.php",
        "https://www.quincyma.gov/contact_us/mayors_office.php",
        "https://www.quincyma.gov/government/elected_officials/city_council/index.php",
    ),
    "plymouth_25023": (
        "https://www.plymouthcountyma.gov/222/Commissioners",
        "https://www.plymouthcountyma.gov/directory.aspx?did=12",
    ),
    "norfolk_25021": (
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
