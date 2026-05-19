"""County-portal host guards for USCM/League municipal matches (mirrors dbt macros)."""

import re


_COUNTY_HOST = re.compile(
    r"(^|\.)[a-z0-9-]*county\.(gov|us)$|(^|\.)county\.[a-z0-9-]+\.(gov|us)$"
)


def _is_county_portal_host(domain: str | None) -> bool:
    d = (domain or "").lower().strip()
    return bool(_COUNTY_HOST.search(d))


def _allows_county_portal_name(name: str | None) -> bool:
    n = (name or "").lower().strip()
    return any(
        x in n
        for x in (
            "macon bibb",
            "macon-bibb",
            "city and county",
            "city-county",
            "city and borough",
            " consolidated",
        )
    )


def blocked(name: str | None, domain: str | None) -> bool:
    return _is_county_portal_host(domain) and not _allows_county_portal_name(name)


def test_hilo_cdp_blocks_hawaiicounty_gov() -> None:
    assert blocked("Hilo CDP", "www.hawaiicounty.gov")


def test_macon_bibb_allows_city_domain() -> None:
    assert not blocked("Macon-Bibb County", "www.maconbibb.us")


def test_parkland_city_uscm_ok() -> None:
    assert not blocked("Parkland city", "www.cityofparkland.org")
