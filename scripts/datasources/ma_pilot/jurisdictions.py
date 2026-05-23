"""
Pilot registry of 10 Massachusetts jurisdictions (8 cities + 2 counties).

``jurisdiction_id`` follows the repo convention ``int_jurisdictions.jurisdiction_id``:
``municipality_{state_fips}{place_fips}`` (zfill 7) and ``county_{state_fips}{county_fips}``
(zfill 5).

Each entry carries a ``homepage`` (used for YouTube channel discovery) plus separate lists
of ``council_seed_urls`` and ``mayor_seed_urls`` so the contact scraper can target the
mayor explicitly — mayors typically live on a single-bio page that does not look like a
roster and would otherwise score below the directory threshold.

All URLs were verified by HTTP probe at registry time. They may rot; the runner skips
non-200 seeds and logs which ones produced rows.
"""

from __future__ import annotations

from typing import TypedDict


class MAJurisdiction(TypedDict):
    jurisdiction_id: str
    state_code: str
    name: str
    type: str
    homepage: str
    council_seed_urls: list[str]
    mayor_seed_urls: list[str]


MA_PILOT_JURISDICTIONS: list[MAJurisdiction] = [
    {
        "jurisdiction_id": "municipality_2507000",
        "state_code": "MA",
        "name": "Boston",
        "type": "city",
        "homepage": "https://www.boston.gov/",
        "council_seed_urls": [
            "https://www.boston.gov/departments/city-council",
        ],
        "mayor_seed_urls": [
            "https://www.boston.gov/departments/mayors-office",
        ],
    },
    {
        "jurisdiction_id": "municipality_2511000",
        "state_code": "MA",
        "name": "Cambridge",
        "type": "city",
        "homepage": "https://www.cambridgema.gov/",
        "council_seed_urls": [
            "https://www.cambridgema.gov/citycouncil",
            "https://www.cambridgema.gov/Departments/citycouncil/members",
        ],
        "mayor_seed_urls": [
            "https://www.cambridgema.gov/Departments/mayorsoffice",
        ],
    },
    {
        "jurisdiction_id": "municipality_2582000",
        "state_code": "MA",
        "name": "Worcester",
        "type": "city",
        "homepage": "https://www.worcesterma.gov/",
        "council_seed_urls": [
            "https://www.worcesterma.gov/city-council",
            "https://www.worcesterma.gov/city-council/councilors",
        ],
        "mayor_seed_urls": [
            "https://www.worcesterma.gov/mayor",
        ],
    },
    {
        "jurisdiction_id": "municipality_2567000",
        "state_code": "MA",
        "name": "Springfield",
        "type": "city",
        "homepage": "https://www.springfield-ma.gov/",
        "council_seed_urls": [
            "https://www.springfield-ma.gov/cos/council",
        ],
        "mayor_seed_urls": [
            "https://www.springfield-ma.gov/cos/mayor0/",
        ],
    },
    {
        "jurisdiction_id": "municipality_2537000",
        "state_code": "MA",
        "name": "Lowell",
        "type": "city",
        "homepage": "https://www.lowellma.gov/",
        "council_seed_urls": [
            "https://www.lowellma.gov/533/Meet-the-City-Council",
            "https://www.lowellma.gov/directory.aspx?did=16",
        ],
        # Lowell uses Plan E (council-manager); the mayor is elected from the council
        # rather than having a separate office page. Mayor's row should fall out of the
        # council roster scrape with title_or_role containing "Mayor".
        "mayor_seed_urls": [],
    },
    {
        "jurisdiction_id": "municipality_2562535",
        "state_code": "MA",
        "name": "Somerville",
        "type": "city",
        "homepage": "https://www.somervillema.gov/",
        "council_seed_urls": [
            "https://www.somervillema.gov/departments/city-council",
        ],
        "mayor_seed_urls": [
            "https://www.somervillema.gov/mayor",
        ],
    },
    {
        "jurisdiction_id": "municipality_2545560",
        "state_code": "MA",
        "name": "Newton",
        "type": "city",
        "homepage": "https://www.newtonma.gov/",
        "council_seed_urls": [
            "https://www.newtonma.gov/government/city-council",
        ],
        # Newton swapped mayors in Jan 2026 (Fuller -> Laredo); legacy /mayor-fuller
        # paths may 404. Runner probes; non-200 seeds are skipped.
        "mayor_seed_urls": [
            "https://www.newtonma.gov/government/mayor",
            "https://www.newtonma.gov/government/mayor-laredo",
        ],
    },
    {
        "jurisdiction_id": "municipality_2555745",
        "state_code": "MA",
        "name": "Quincy",
        "type": "city",
        "homepage": "https://www.quincyma.gov/",
        "council_seed_urls": [
            "https://www.quincyma.gov/government/elected_officials/city_council/index.php",
        ],
        "mayor_seed_urls": [
            "https://www.quincyma.gov/government/elected_officials/mayor_s_office/index.php",
            "https://www.quincyma.gov/contact_us/mayors_office.php",
        ],
    },
    {
        "jurisdiction_id": "county_25023",
        "state_code": "MA",
        "name": "Plymouth County",
        "type": "county",
        "homepage": "https://www.plymouthcountyma.gov/",
        "council_seed_urls": [
            "https://www.plymouthcountyma.gov/222/Commissioners",
            "https://www.plymouthcountyma.gov/directory.aspx?did=12",
        ],
        # No mayor for a MA county — chair of commissioners is the closest analog and
        # will be extracted from the commissioners roster.
        "mayor_seed_urls": [],
    },
    {
        "jurisdiction_id": "county_25021",
        "state_code": "MA",
        "name": "Norfolk County",
        "type": "county",
        "homepage": "http://www.norfolkcounty.org/",
        "council_seed_urls": [
            "http://www.norfolkcounty.org/county_commission/commissioners.php",
        ],
        "mayor_seed_urls": [],
    },
]
