"""Find the Granicus and Legistar portals to read (#536).

1. **The #460 survey first.** ``bronze.bronze_jurisdiction_meeting_source`` (written by
   :mod:`scrapers.discovery.survey_meeting_sources`) lists the Granicus and Legistar
   portals of the governments around each data center site.
2. **Then known URL patterns.** For other governments (the surveyed ones without a
   Legistar portal first, then the most populous counties and cities in data center
   states), each candidate client slug (``dakota``, ``fultoncountyga``, the
   government's Granicus subdomain, ...) is checked two ways: the Web API must serve
   data for it, and the client's own calendar page must name the government and its
   state (:func:`scrapers.discovery.survey_meeting_sources.vendor_page_matches`). A
   slug that only answers the API is not counted: it could be another government.

Granicus portals are not found by URL pattern: their pages are disallowed by
robots.txt, so a guessed host could not be confirmed as the government's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import urlsplit

from loguru import logger

from scrapers.discovery.survey_meeting_sources import (
    STATE_NAMES,
    Government,
    _core_name,
    names_government,
    vendor_page_matches,
    vendor_slugs,
)
from scrapers.platforms.http import PlatformFetchError, PoliteClient
from scrapers.platforms.legistar import client_is_configured

SURVEY_TABLE = "bronze.bronze_jurisdiction_meeting_source"


@dataclass
class PortalTarget:
    platform: str  # 'legistar' | 'granicus'
    portal: str  # Legistar client slug or Granicus host
    jurisdiction_id: Optional[str]
    state_code: Optional[str]
    found_via: str = "survey"
    data_center: bool = False
    granicus_host: Optional[str] = None  # for a Legistar client: the same government's Granicus host
    name: Optional[str] = None


@dataclass
class Candidate:
    """A government to probe by URL pattern."""

    government: Government
    data_center: bool = False
    extra_slugs: list[str] = field(default_factory=list)


def _host(url: str) -> str:
    return (urlsplit(url if "//" in url else "https://" + url).hostname or "").lower()


def legistar_client_from_url(url: str) -> Optional[str]:
    host = _host(url)
    if host.endswith(".legistar.com") and not host.startswith("webapi."):
        return host.split(".")[0]
    m = re.match(r"https?://webapi\.legistar\.com/v1/([^/?#]+)", url, re.I)
    return m.group(1).lower() if m else None


def survey_targets(rows: Iterable[dict[str, Any]]) -> list[PortalTarget]:
    """Portal targets from survey rows (``jurisdiction_id, state_code, platform, url, data_center_site_id``).

    One target per (platform, portal). A Legistar target carries the same government's
    Granicus host, so a Legistar event's Granicus clip id can become a video URL.
    """
    granicus_by_gov: dict[str, str] = {}
    rows = list(rows)
    for r in rows:
        if r["platform"] == "granicus":
            granicus_by_gov.setdefault(r["jurisdiction_id"], _host(r["url"]))
    targets: dict[tuple[str, str], PortalTarget] = {}
    for r in rows:
        dc = r.get("data_center_site_id") is not None
        if r["platform"] == "granicus":
            host = _host(r["url"])
            key = ("granicus", host)
        elif r["platform"] == "legistar":
            client = legistar_client_from_url(r["url"])
            if not client:
                continue
            key = ("legistar", client)
        else:
            continue
        if key in targets:
            targets[key].data_center = targets[key].data_center or dc
            continue
        targets[key] = PortalTarget(
            platform=key[0],
            portal=key[1],
            jurisdiction_id=r["jurisdiction_id"],
            state_code=r.get("state_code"),
            found_via="survey",
            data_center=dc,
            granicus_host=granicus_by_gov.get(r["jurisdiction_id"]) if key[0] == "legistar" else None,
        )
    return sorted(targets.values(), key=lambda t: (t.platform, t.portal))


def candidate_slugs(c: Candidate) -> list[str]:
    seen: list[str] = []
    for slug in [*c.extra_slugs, *vendor_slugs(c.government)]:
        slug = slug.lower()
        if slug and slug not in seen:
            seen.append(slug)
    return seen


_HREF = re.compile(r"""href\s*=\s*["']https?://([^/"'?#:]+)""", re.I)
_VENDOR_HOSTS = ("legistar", "granicus", "microsoft", "google", "adobe", "telerik", "facebook", "twitter", "x.com")


def official_site_names_state(html: str, gov: Government) -> bool:
    """The page links the government's own website on a state-specific domain.

    Calendar pages often say "Fulton County - Meeting Calendar" without the state; their
    link home (``fultoncountyga.gov``, ``co.dakota.mn.us``) carries it.
    """
    core = re.sub(r"[^a-z0-9]", "", _core_name(gov).lower())
    st = gov.state_code.lower()
    if not core or not st:
        return False
    for host in {h.lower() for h in _HREF.findall(html)}:
        if any(v in host for v in _VENDOR_HOSTS) or core not in host.replace("-", ""):
            continue
        flat = host.replace("-", "")
        if re.search(rf"(^|\.){st}\.(us|gov)$", host) or re.search(rf"\.{st}\.us$", host):
            return True
        if re.search(rf"{core}(county|city|cityof|co|town|parish)?{st}\.", flat):
            return True
    return False


async def confirm_legistar(http: PoliteClient, slug: str, gov: Government) -> bool:
    """The Web API serves ``slug`` and its calendar page names this government and its state.

    The state can come from the page text, the slug (``abilenetx``) or the page's link to
    the government's own state-specific website.
    """
    if not await client_is_configured(http, slug):
        return False
    url = f"https://{slug}.legistar.com/Calendar.aspx"
    try:
        page = await http.get(url)
    except PlatformFetchError as exc:
        logger.info("legistar {}: API answers but the calendar page could not be read ({})", slug, exc.status)
        return False
    if vendor_page_matches(page.text, url, gov):
        return True
    text = re.sub(r"<[^>]+>", " ", page.text)
    return names_government(text, gov) and official_site_names_state(page.text, gov)


async def probe_legistar(
    http: PoliteClient,
    candidates: Sequence[Candidate],
    *,
    target: int,
    max_probes: int,
    skip_clients: Iterable[str] = (),
    granicus_hosts: Optional[dict[str, str]] = None,
) -> tuple[list[PortalTarget], int]:
    """Probe candidates in order until ``target`` portals are confirmed. Returns (targets, governments probed)."""
    found: list[PortalTarget] = []
    taken = {s.lower() for s in skip_clients}
    probed = 0
    for c in candidates:
        if len(found) >= target or probed >= max_probes:
            break
        probed += 1
        for slug in candidate_slugs(c):
            if slug in taken:
                continue
            if await confirm_legistar(http, slug, c.government):
                taken.add(slug)
                g = c.government
                found.append(
                    PortalTarget(
                        platform="legistar",
                        portal=slug,
                        jurisdiction_id=g.jurisdiction_id,
                        state_code=g.state_code,
                        found_via="url_pattern",
                        data_center=c.data_center,
                        granicus_host=(granicus_hosts or {}).get(g.jurisdiction_id),
                        name=g.name,
                    )
                )
                logger.success("legistar portal found by URL pattern: {} -> {} ({})", slug, g.name, g.state_code)
                break
    return found, probed


# --------------------------------------------------------------------------------
# Warehouse reads
# --------------------------------------------------------------------------------


def _gov(row: dict[str, Any]) -> Government:
    sc = str(row.get("state_code") or "").strip()
    return Government(
        jurisdiction_id=str(row["jurisdiction_id"]),
        geoid=row.get("geoid"),
        name=str(row.get("name") or ""),
        state_code=sc,
        state=str(row.get("state") or STATE_NAMES.get(sc, "")),
        # gold.jurisdictions says 'city' / 'town'; the survey's name matching says 'municipality'.
        jurisdiction_type="county" if row.get("jurisdiction_type") == "county" else "municipality",
    )


def load_survey_rows(cur: Any) -> list[dict[str, Any]]:
    cur.execute(
        f"SELECT jurisdiction_id, state_code, platform, url, data_center_site_id FROM {SURVEY_TABLE} "
        "WHERE platform IN ('granicus', 'legistar') ORDER BY jurisdiction_id, platform, url"
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def load_candidates(cur: Any, exclude_jurisdictions: Iterable[str], limit: int) -> list[Candidate]:
    """Surveyed data center governments without a Legistar portal, then populous governments in data center states."""
    exclude = sorted(set(exclude_jurisdictions))
    cur.execute(
        f"""
        WITH surveyed AS (
            SELECT jurisdiction_id,
                   bool_or(data_center_site_id IS NOT NULL) AS dc,
                   max(CASE WHEN platform = 'granicus' THEN split_part(split_part(url, '//', 2), '.', 1) END) AS granicus_slug
            FROM {SURVEY_TABLE} GROUP BY jurisdiction_id
        ),
        dc_states AS (SELECT DISTINCT state_code FROM public.data_center_site WHERE state_code IS NOT NULL)
        SELECT j.jurisdiction_id, j.geoid, j.name, j.jurisdiction_type, j.state_code, j.state_name AS state,
               s.jurisdiction_id IS NOT NULL AS surveyed, coalesce(s.dc, false) AS dc, s.granicus_slug,
               j.population
        FROM gold.jurisdictions j
        LEFT JOIN surveyed s ON s.jurisdiction_id = j.jurisdiction_id
        WHERE j.jurisdiction_type IN ('county', 'city', 'town')
          AND (s.jurisdiction_id IS NOT NULL OR j.state_code IN (SELECT state_code FROM dc_states))
          AND NOT (j.jurisdiction_id = ANY(%s))
        ORDER BY (s.jurisdiction_id IS NOT NULL) DESC, j.population DESC NULLS LAST, j.jurisdiction_id
        LIMIT %s
        """,
        (exclude, limit),
    )
    cols = [d[0] for d in cur.description]
    out: list[Candidate] = []
    for r in (dict(zip(cols, row)) for row in cur.fetchall()):
        extra = [r["granicus_slug"]] if r.get("granicus_slug") else []
        out.append(Candidate(government=_gov(r), data_center=bool(r["dc"]), extra_slugs=extra))
    return out
