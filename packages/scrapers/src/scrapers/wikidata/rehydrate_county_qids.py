"""
Audit and repair county Wikidata Q-ids in ``bronze.bronze_jurisdictions_counties_wikidata``.

Issue #461: an earlier hydration matched counties to Wikidata items by the bare
3-digit county code, so many counties carry another state's item (Allen County,
Indiana, 18003, had Baldwin County, Alabama's Q156163) and with it that item's
website, socials and statistics.

This module checks every county row against Wikidata itself:

1. AUDIT: for each Q-id on a row, read its FIPS (``P882``) and the FIPS of its
   ``P131`` state (``P5087``) from WDQS. A row is *mismatched* when none of its
   item's ``P882`` values equals the row's 5-digit GEOID.
2. RESOLVE: for each mismatched row, find the item whose ``P882`` is exactly the
   GEOID and whose state agrees (``fips_match.county_item_matches``). Two items
   for one GEOID count as ambiguous and are not guessed.
3. HYDRATE: read the resolved items with ``wbgetentities`` and rewrite every
   item-derived column. A row with no trustworthy item has those columns cleared:
   no value is better than another county's value.

Dry run by default: it reads Wikidata (free public endpoints) and the local
warehouse and writes a JSON report (old vs. new Q-id and website per row) under
``data/cache/wikidata_corrections/``. ``--apply`` also rewrites the rows. Either
way it only connects to a local Postgres (localhost/127.0.0.1) and refuses any
other host, Neon included. Wikidata itself is never edited.

Examples::

  python -m scrapers.wikidata.rehydrate_county_qids               # dry run, all states
  python -m scrapers.wikidata.rehydrate_county_qids --states IN,OK
  python -m scrapers.wikidata.rehydrate_county_qids --apply
"""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

import httpx
from loguru import logger

from core_lib.paths import repo_root
from scrapers.wikidata.fips_match import (
    county_item_matches,
    county_p882_to_geoid,
    normalize_county_geoid,
)
from scrapers.wikidata.state_fips import STATE_FIPS

COUNTY_TABLE = "bronze.bronze_jurisdictions_counties_wikidata"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIBASE_API = "https://www.wikidata.org/w/api.php"
# Generic client name; Wikimedia asks automated clients for a descriptive UA.
USER_AGENT = "open-navigator-data/1.0 (county FIPS audit; python-httpx)"
SQ_KM = "http://www.wikidata.org/entity/Q712226"
SQ_MI = "http://www.wikidata.org/entity/Q232291"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Every column on the bronze row that came from the Wikidata item.
ITEM_COLUMNS: Tuple[str, ...] = (
    "wikidata_id",
    "official_website",
    "official_image_url",
    "page_banner_image",
    "locator_map_image",
    "youtube_channel_id",
    "youtube_channel_url",
    "facebook_username",
    "facebook_url",
    "twitter_username",
    "twitter_url",
    "population",
    "area_sq_km",
    "per_capita_income",
    "number_of_households",
    "median_age",
    "time_zone",
    "local_dialing_code",
    "google_maps_customer_id",
    "language_of_work_or_name",
    "head_of_government",
    "head_of_government_position",
    "head_of_government_start_time",
    "postal_codes",
    "latitude",
    "longitude",
    "wikidata_fips_code",
    "wikidata_gnis_id",
    "wikidata_nces_id",
    "wikidata_last_updated",
)


def load_env(env_file: Optional[Path] = None) -> None:
    """Load the repo ``.env`` (without overriding variables already set)."""
    path = env_file or repo_root(__file__) / ".env"
    if not path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional; plain env vars still work
        logger.debug("python-dotenv not installed; skipping {}", path)
        return
    load_dotenv(path, override=False)


def local_database_url() -> str:
    """The local warehouse URL. Never a Neon/core_lib default: those point at the cloud.

    ``OPEN_NAVIGATOR_LOCAL_DATABASE_URL`` wins, then ``OPEN_NAVIGATOR_DATABASE_URL``
    when it names a local host, then ``POSTGRES_*`` on localhost:5433.
    """
    explicit = (os.getenv("OPEN_NAVIGATOR_LOCAL_DATABASE_URL") or "").strip()
    if explicit:
        return explicit
    on_url = (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
    if on_url and is_local_database(on_url):
        return on_url
    user = os.getenv("POSTGRES_USER", "postgres")
    pwd = os.getenv("POSTGRES_PASSWORD", "password")
    port = os.getenv("POSTGRES_PORT", "5433")
    return f"postgresql://{user}:{pwd}@localhost:{port}/open_navigator"


def redact_url(url: str) -> str:
    """``url`` with the password removed, safe to log."""
    p = urlparse(url)
    return f"{p.scheme}://{p.username or ''}@{p.hostname or ''}:{p.port or ''}{p.path}"


def is_local_database(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in LOCAL_HOSTS


# ---------------------------------------------------------------------------
# Wikidata access (WDQS + wbgetentities), paced and cached
# ---------------------------------------------------------------------------


class WikidataReader:
    def __init__(
        self,
        *,
        pause_s: float = 2.0,
        timeout_s: float = 120.0,
        max_retry_wait_s: float = 120.0,
        attempts: int = 10,
    ) -> None:
        self.pause_s = pause_s
        # Wikimedia's edge sometimes answers a light, paced client with 429 and
        # Retry-After: 1000 while the next request succeeds; cap the wait.
        self.max_retry_wait_s = max_retry_wait_s
        self.attempts = attempts
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._last = 0.0

    def close(self) -> None:
        self._client.close()

    def _wait(self) -> None:
        delta = time.monotonic() - self._last
        if delta < self.pause_s:
            time.sleep(self.pause_s - delta)
        self._last = time.monotonic()

    def _get(self, url: str, params: Mapping[str, str], accept: str) -> Any:
        for attempt in range(self.attempts):
            self._wait()
            try:
                resp = self._client.get(url, params=params, headers={"Accept": accept})
            except httpx.TransportError as exc:
                logger.warning("Wikidata request failed ({}), retrying", exc)
                time.sleep(5 * (attempt + 1))
                continue
            if resp.status_code in (429, 500, 502, 503, 504):
                retry = resp.headers.get("Retry-After")
                wait = float(retry) if retry and retry.isdigit() else 10.0 * (attempt + 1)
                wait = min(wait, self.max_retry_wait_s, 15.0 * (attempt + 1))
                logger.warning("Wikidata HTTP {} — waiting {:.0f}s", resp.status_code, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Wikidata request kept failing: {url}")

    def sparql(self, query: str) -> List[Dict[str, str]]:
        data = self._get(
            SPARQL_ENDPOINT,
            {"query": query, "format": "json"},
            "application/sparql-results+json",
        )
        return [
            {k: v.get("value") for k, v in b.items()}
            for b in data.get("results", {}).get("bindings", [])
        ]

    def get_entities(self, qids: Sequence[str], props: str = "info|labels|claims") -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        ids = [q for q in qids if str(q).startswith("Q")]
        for i in range(0, len(ids), 50):
            data = self._get(
                WIKIBASE_API,
                {
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(ids[i : i + 50]),
                    "props": props,
                    "languages": "en",
                },
                "application/json",
            )
            out.update({k: v for k, v in (data.get("entities") or {}).items() if k.startswith("Q")})
        return out


def _qid(uri: Optional[str]) -> Optional[str]:
    if not uri:
        return None
    q = uri.rsplit("/", 1)[-1]
    return q if q.startswith("Q") else None


def _chunks(xs: Sequence[str], n: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


def fetch_item_fips(reader: WikidataReader, qids: Sequence[str], batch: int = 200) -> Dict[str, Dict[str, Any]]:
    """qid → {"p882": set, "state_fips": set, "label": str} for the given items."""
    out: Dict[str, Dict[str, Any]] = {q: {"p882": set(), "state_fips": set(), "label": ""} for q in qids}
    done = 0
    for chunk in _chunks(list(qids), batch):
        values = " ".join(f"wd:{q}" for q in chunk)
        rows = reader.sparql(
            f"""
            SELECT ?item ?itemLabel ?fips ?stFips WHERE {{
              VALUES ?item {{ {values} }}
              OPTIONAL {{ ?item wdt:P882 ?fips . }}
              OPTIONAL {{ ?item wdt:P131 ?st . ?st wdt:P5087 ?stFips . }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
            }}
            """
        )
        for r in rows:
            q = _qid(r.get("item"))
            if not q or q not in out:
                continue
            if r.get("fips"):
                out[q]["p882"].add(r["fips"])
            if r.get("stFips"):
                out[q]["state_fips"].add(r["stFips"])
            out[q]["label"] = r.get("itemLabel") or out[q]["label"]
        done += len(chunk)
        logger.info("  item FIPS: {}/{} items read", done, len(qids))
    return out


Candidate = Tuple[str, Optional[str], bool]  # (qid, state FIPS of its P131 state, is a US county)


def fetch_items_by_fips(
    reader: WikidataReader, geoids: Sequence[str], batch: int = 200
) -> Dict[str, List[Candidate]]:
    """geoid → candidates for items whose P882 is exactly that GEOID."""
    out: Dict[str, List[Candidate]] = {g: [] for g in geoids}
    for chunk in _chunks(list(geoids), batch):
        values = " ".join(f'"{g}"' for g in chunk)
        rows = reader.sparql(
            f"""
            SELECT DISTINCT ?item ?fips ?stFips ?isCounty WHERE {{
              VALUES ?fips {{ {values} }}
              ?item wdt:P882 ?fips .
              OPTIONAL {{ ?item wdt:P131 ?st . ?st wdt:P5087 ?stFips . }}
              OPTIONAL {{ ?item wdt:P31/wdt:P279* wd:Q47168 . BIND(true AS ?isCounty) }}
            }}
            """
        )
        for r in rows:
            q = _qid(r.get("item"))
            g = r.get("fips")
            if q and g in out:
                out[g].append((q, r.get("stFips"), r.get("isCounty") == "true"))
    return out


# ---------------------------------------------------------------------------
# Pure decision logic (unit-tested)
# ---------------------------------------------------------------------------


def item_matches_row(geoid: str, item: Mapping[str, Any]) -> bool:
    """True when the item's own P882 is the row's GEOID (state agreeing when known)."""
    states = item.get("state_fips") or set()
    p882 = item.get("p882") or set()
    if not states:
        return county_item_matches(geoid, p882, None)
    return any(county_item_matches(geoid, p882, sf) for sf in states)


def resolve_county_qid(geoid: str, candidates: Iterable[Sequence[Any]]) -> Tuple[Optional[str], str]:
    """Pick the single item for a GEOID. Returns (qid, reason).

    Each candidate is ``(qid, state_fips, is_county)``; ``is_county`` is optional.
    Items in another state are dropped. When two items remain and exactly one is
    a US county (``P31/P279*`` Q47168), that one wins (a village that wrongly
    carries the county's FIPS loses); otherwise the GEOID is ambiguous.
    """
    g = normalize_county_geoid(geoid)
    if not g:
        return None, "bad_geoid"
    keep: Dict[str, bool] = {}
    for cand in candidates:
        qid, state_fips = cand[0], cand[1]
        is_county = bool(cand[2]) if len(cand) > 2 else False
        if state_fips and not g.startswith(str(state_fips).zfill(2)):
            continue  # an item in another state that happens to carry this code
        keep[qid] = keep.get(qid, False) or is_county
    if not keep:
        return None, "no_item"
    if len(keep) == 1:
        return next(iter(keep)), "resolved"
    counties = [q for q, c in keep.items() if c]
    if len(counties) == 1:
        return counties[0], "resolved_county_type"
    return None, "ambiguous"


def _sv(claims: Mapping[str, Any], pid: str) -> Any:
    """Value of the first preferred-or-normal claim for ``pid``."""
    cs = [c for c in (claims.get(pid) or []) if c.get("rank") != "deprecated"]
    if not cs:
        return None
    preferred = [c for c in cs if c.get("rank") == "preferred"]
    snak = ((preferred or cs)[0] or {}).get("mainsnak") or {}
    dv = snak.get("datavalue")
    return None if dv is None else dv.get("value")


def _claim(claims: Mapping[str, Any], pid: str) -> Optional[Mapping[str, Any]]:
    cs = [c for c in (claims.get(pid) or []) if c.get("rank") != "deprecated"]
    if not cs:
        return None
    preferred = [c for c in cs if c.get("rank") == "preferred"]
    return (preferred or cs)[0]


def _amount(v: Any) -> Optional[float]:
    if isinstance(v, dict) and v.get("amount") is not None:
        try:
            return float(str(v["amount"]).lstrip("+"))
        except ValueError:
            return None
    return None


def _commons(fn: Any) -> Optional[str]:
    if not isinstance(fn, str) or not fn:
        return None
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{fn.replace(' ', '_')}"


def _entity_ref(v: Any) -> Optional[str]:
    if isinstance(v, dict) and v.get("id"):
        return str(v["id"])
    return None


def _time(v: Any) -> Optional[str]:
    if isinstance(v, dict) and isinstance(v.get("time"), str):
        t = v["time"].lstrip("+")
        # Wikidata writes month/day 00 for year-only precision.
        t = t.replace("-00-00T", "-01-01T").replace("-00T", "-01T")
        return t.rstrip("Z")
    return None


def referenced_qids(entity: Mapping[str, Any]) -> Set[str]:
    claims = entity.get("claims") or {}
    out: Set[str] = set()
    for pid in ("P6", "P421", "P1313", "P407"):
        r = _entity_ref(_sv(claims, pid))
        if r:
            out.add(r)
    return out


def entity_to_row(
    entity: Mapping[str, Any], qid: str, labels: Mapping[str, str]
) -> Dict[str, Any]:
    """Map a ``wbgetentities`` item onto the bronze county columns in ``ITEM_COLUMNS``."""
    claims = entity.get("claims") or {}
    row: Dict[str, Any] = {c: None for c in ITEM_COLUMNS}
    row["wikidata_id"] = qid

    site = _sv(claims, "P856")
    row["official_website"] = site if isinstance(site, str) else None
    row["official_image_url"] = _commons(_sv(claims, "P18"))
    row["locator_map_image"] = _commons(_sv(claims, "P242"))
    row["page_banner_image"] = _commons(_sv(claims, "P948"))

    yt = _sv(claims, "P2397")
    if isinstance(yt, str) and yt:
        row["youtube_channel_id"] = yt
        row["youtube_channel_url"] = f"https://www.youtube.com/channel/{yt}"
    fb = _sv(claims, "P2013")
    if isinstance(fb, str) and fb:
        row["facebook_username"] = fb
        row["facebook_url"] = f"https://www.facebook.com/{fb}"
    tw = _sv(claims, "P2002")
    if isinstance(tw, str) and tw:
        tw = tw.strip().lstrip("@")
        row["twitter_username"] = tw
        row["twitter_url"] = f"https://twitter.com/{tw}"

    pop = _amount(_sv(claims, "P1082"))
    row["population"] = int(pop) if pop is not None else None
    area_v = _sv(claims, "P2046")
    area = _amount(area_v)
    if area is not None and isinstance(area_v, dict):
        unit = area_v.get("unit")
        if unit == SQ_KM:
            row["area_sq_km"] = area
        elif unit == SQ_MI:
            row["area_sq_km"] = area * 2.589988110336
    pci = _amount(_sv(claims, "P3529"))
    row["per_capita_income"] = int(pci) if pci is not None else None
    row["number_of_households"] = _amount(_sv(claims, "P1538"))
    row["median_age"] = _amount(_sv(claims, "P1310"))

    for col, pid in (
        ("time_zone", "P421"),
        ("language_of_work_or_name", "P407"),
        ("head_of_government_position", "P1313"),
    ):
        ref = _entity_ref(_sv(claims, pid))
        row[col] = labels.get(ref) if ref else None
    hog = _claim(claims, "P6")
    if hog:
        ref = _entity_ref(((hog.get("mainsnak") or {}).get("datavalue") or {}).get("value"))
        row["head_of_government"] = labels.get(ref) if ref else None
        starts = (hog.get("qualifiers") or {}).get("P580") or []
        if starts:
            row["head_of_government_start_time"] = _time((starts[0].get("datavalue") or {}).get("value"))

    for col, pid in (("local_dialing_code", "P473"), ("google_maps_customer_id", "P3749")):
        v = _sv(claims, pid)
        row[col] = v if isinstance(v, str) else None
    postal = [
        (c.get("mainsnak") or {}).get("datavalue", {}).get("value")
        for c in (claims.get("P281") or [])
        if c.get("rank") != "deprecated"
    ]
    postal = [p for p in postal if isinstance(p, str)]
    row["postal_codes"] = json.dumps(postal) if postal else None

    coord = _sv(claims, "P625")
    if isinstance(coord, dict) and coord.get("latitude") is not None:
        row["latitude"] = float(coord["latitude"])
        row["longitude"] = float(coord["longitude"])

    fips = _sv(claims, "P882")
    row["wikidata_fips_code"] = county_p882_to_geoid(fips) or (fips if isinstance(fips, str) else None)
    gnis = _sv(claims, "P590")
    row["wikidata_gnis_id"] = gnis if isinstance(gnis, str) else None
    nces = _sv(claims, "P6545")
    row["wikidata_nces_id"] = nces if isinstance(nces, str) else None
    modified = entity.get("modified")
    row["wikidata_last_updated"] = modified.rstrip("Z") if isinstance(modified, str) else None
    return row


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class AuditResult:
    rows: List[Tuple[str, str, Optional[str]]]
    items: Dict[str, Dict[str, Any]]
    mismatched: List[Tuple[str, str, str]] = field(default_factory=list)
    resolutions: Dict[str, Tuple[Optional[str], str]] = field(default_factory=dict)
    # Rows whose item is right but whose stored wikidata_fips_code is not the GEOID.
    restamp: List[str] = field(default_factory=list)


def read_rows(conn, states: Optional[List[str]]) -> List[Tuple[str, str, Optional[str]]]:
    sql = f"SELECT geoid::text, usps::text, NULLIF(BTRIM(wikidata_id), '') FROM {COUNTY_TABLE}"
    params: Tuple[Any, ...] = ()
    if states:
        sql += " WHERE usps = ANY(%s)"
        params = (states,)
    with conn.cursor() as cur:
        cur.execute(sql + " ORDER BY geoid", params)
        return [(g, u, q) for g, u, q in cur.fetchall()]


def read_current(conn, geoids: Sequence[str]) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """geoid → (name, official_website) as stored now, for the report."""
    if not geoids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT geoid::text, name, official_website FROM {COUNTY_TABLE} WHERE geoid = ANY(%s)",
            (list(geoids),),
        )
        return {g: (n, w) for g, n, w in cur.fetchall()}


def read_stale_fips(conn, states: Optional[List[str]]) -> Set[str]:
    """GEOIDs with a Q-id whose stored ``wikidata_fips_code`` is not the GEOID."""
    sql = (
        f"SELECT geoid::text FROM {COUNTY_TABLE} "
        "WHERE NULLIF(BTRIM(wikidata_id), '') IS NOT NULL "
        "AND REPLACE(BTRIM(COALESCE(wikidata_fips_code, '')), '-', '') "
        "IS DISTINCT FROM REPLACE(BTRIM(geoid::text), '-', '')"
    )
    params: Tuple[Any, ...] = ()
    if states:
        sql += " AND usps = ANY(%s)"
        params = (states,)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return {g for (g,) in cur.fetchall()}


def apply_restamp(conn, geoids: Sequence[str]) -> int:
    """Set ``wikidata_fips_code`` to the GEOID on rows whose item was verified."""
    if not geoids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE {COUNTY_TABLE} SET wikidata_fips_code = geoid::text WHERE geoid = ANY(%s)",
            (list(geoids),),
        )
        n = cur.rowcount
    conn.commit()
    return n


def audit(conn, reader: WikidataReader, states: Optional[List[str]]) -> AuditResult:
    rows = read_rows(conn, states)
    qids = sorted({q for _g, _u, q in rows if q})
    logger.info("Auditing {:,} county rows ({:,} distinct Q-ids)", len(rows), len(qids))
    items = fetch_item_fips(reader, qids)
    res = AuditResult(rows=rows, items=items)
    for geoid, usps, qid in rows:
        if qid and not item_matches_row(geoid, items.get(qid, {})):
            res.mismatched.append((geoid, usps, qid))
    logger.info("Mismatched rows (item P882 ≠ geoid): {:,}", len(res.mismatched))
    wrong = {g for g, _u, _q in res.mismatched}
    res.restamp = sorted(read_stale_fips(conn, states) - wrong)
    logger.info("Right item, stale wikidata_fips_code: {:,}", len(res.restamp))
    if res.mismatched:
        by_fips = fetch_items_by_fips(reader, [g for g, _u, _q in res.mismatched])
        for geoid, usps, _q in res.mismatched:
            sf = STATE_FIPS.get(usps)
            if sf and not geoid.startswith(sf):
                res.resolutions[geoid] = (None, "geoid_state_disagree")
                continue
            res.resolutions[geoid] = resolve_county_qid(geoid, by_fips.get(geoid, []))
    return res


def hydrate_rows(reader: WikidataReader, qids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    entities = reader.get_entities(list(qids))
    refs: Set[str] = set()
    for e in entities.values():
        refs |= referenced_qids(e)
    labels: Dict[str, str] = {}
    if refs:
        for q, e in reader.get_entities(sorted(refs), props="labels").items():
            lab = ((e.get("labels") or {}).get("en") or {}).get("value")
            if lab:
                labels[q] = lab
    return {q: entity_to_row(e, q, labels) for q, e in entities.items()}


def apply_updates(conn, updates: List[Tuple[str, Dict[str, Any]]], fetched_at: datetime) -> int:
    cols = list(ITEM_COLUMNS)
    set_sql = ", ".join(f"{c} = %s" for c in cols)
    sql = (
        f"UPDATE {COUNTY_TABLE} SET {set_sql}, wikidata_fetched_at = %s, "
        "official_website_updated_at = %s WHERE geoid = %s"
    )
    n = 0
    with conn.cursor() as cur:
        for geoid, row in updates:
            cur.execute(sql, [row.get(c) for c in cols] + [fetched_at, fetched_at, geoid])
            n += cur.rowcount
    conn.commit()
    return n


def plan_updates(
    res: AuditResult, hydrated: Mapping[str, Mapping[str, Any]]
) -> List[Tuple[str, Dict[str, Any]]]:
    """(geoid, new item columns) for every mismatched row.

    A resolved row gets its item's columns, with ``wikidata_fips_code`` set to the
    GEOID the item was matched on (its P882 equals it by construction, even when
    the first claim is a short or alternate form). An unresolved row gets every
    item column cleared.
    """
    updates: List[Tuple[str, Dict[str, Any]]] = []
    for geoid, _usps, _old in res.mismatched:
        q, _why = res.resolutions.get(geoid, (None, "no_item"))
        row = dict(hydrated[q]) if q and q in hydrated else None
        if row is None:
            row = {c: None for c in ITEM_COLUMNS}
        else:
            row["wikidata_fips_code"] = geoid
        updates.append((geoid, row))
    return updates


def summarize(
    res: AuditResult,
    updates: Sequence[Tuple[str, Mapping[str, Any]]],
    current: Mapping[str, Tuple[Optional[str], Optional[str]]],
) -> Dict[str, int]:
    """Counts for the report: wrong websites before, how many get a right one, how many are cleared."""
    new_by_geoid = {g: r for g, r in updates}
    wrong_site = corrected = cleared = unchanged_site = 0
    for geoid, _u, _q in res.mismatched:
        old_site = (current.get(geoid) or (None, None))[1]
        if not (old_site or "").strip():
            continue
        wrong_site += 1
        new_site = (new_by_geoid.get(geoid) or {}).get("official_website")
        if not new_site:
            cleared += 1
        elif new_site.strip().rstrip("/").lower() == old_site.strip().rstrip("/").lower():
            unchanged_site += 1
        else:
            corrected += 1
    return {
        "rows_with_wrong_item_website": wrong_site,
        "websites_replaced_with_own_item": corrected,
        "websites_cleared_no_own_website": cleared,
        "websites_same_after_fix": unchanged_site,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--states", default="", help="Comma-separated USPS codes (default: all)")
    ap.add_argument("--apply", action="store_true", help="Write to the local bronze table")
    ap.add_argument("--database-url", default="", help="Postgres URL (default: local :5433)")
    ap.add_argument("--env-file", type=Path, default=None, help="Env file (default: <repo>/.env)")
    ap.add_argument("--pause", type=float, default=2.0, help="Seconds between Wikidata requests")
    ap.add_argument(
        "--max-retry-wait",
        type=float,
        default=120.0,
        help="Cap on the wait after a Wikidata 429/5xx (seconds)",
    )
    ap.add_argument(
        "--report",
        type=Path,
        default=None,
        help="JSON report path (default: data/cache/wikidata_corrections/county_qid_audit_<ts>.json)",
    )
    args = ap.parse_args(argv)

    import psycopg2

    load_env(args.env_file)
    db_url = args.database_url.strip() or local_database_url()
    if not is_local_database(db_url):
        # Even the read-only audit stays on the local warehouse: this tool is not for Neon.
        raise SystemExit("Only a local Postgres (localhost) is supported; refusing this host.")
    states = [s.strip().upper() for s in args.states.split(",") if s.strip()] or None
    logger.info("Database: {}", redact_url(db_url))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = args.report or (
        repo_root(__file__) / "data/cache/wikidata_corrections" / f"county_qid_audit_{stamp}.json"
    )
    report.parent.mkdir(parents=True, exist_ok=True)

    reader = WikidataReader(pause_s=args.pause, max_retry_wait_s=args.max_retry_wait)
    conn = psycopg2.connect(db_url)
    try:
        res = audit(conn, reader, states)
        reasons: Dict[str, int] = {}
        for _q, why in res.resolutions.values():
            reasons[why] = reasons.get(why, 0) + 1
        logger.info("Resolutions: {}", reasons)

        new_qids = sorted({q for q, _w in res.resolutions.values() if q})
        hydrated = hydrate_rows(reader, new_qids) if new_qids else {}
        updates = plan_updates(res, hydrated)
        current = read_current(conn, [g for g, _u, _q in res.mismatched])
        counts = summarize(res, updates, current)
        logger.info("Website counts: {}", counts)
        new_by_geoid = dict(updates)

        payload = {
            "generated_at": stamp,
            "states": states or "all",
            "rows_audited": len(res.rows),
            "distinct_qids": len(res.items),
            "mismatched": len(res.mismatched),
            "resolutions": reasons,
            "website_counts": counts,
            "fips_restamped": res.restamp,
            "applied": bool(args.apply),
            "changes": [
                {
                    "geoid": g,
                    "usps": u,
                    "name": (current.get(g) or (None, None))[0],
                    "old_qid": old,
                    "old_item_label": res.items.get(old, {}).get("label"),
                    "old_item_p882": sorted(res.items.get(old, {}).get("p882", [])),
                    "old_official_website": (current.get(g) or (None, None))[1],
                    "new_qid": res.resolutions.get(g, (None, ""))[0],
                    "reason": res.resolutions.get(g, (None, ""))[1],
                    "new_official_website": new_by_geoid[g].get("official_website"),
                }
                for g, u, old in res.mismatched
            ],
        }
        report.write_text(json.dumps(payload, indent=2, default=str))
        logger.success("Audit report → {}", report)

        if args.apply:
            n = apply_updates(conn, updates, datetime.now(timezone.utc).replace(tzinfo=None))
            logger.success("Rewrote {:,} county rows in {}", n, COUNTY_TABLE)
            n = apply_restamp(conn, res.restamp)
            logger.success("Restamped wikidata_fips_code on {:,} rows with the right item", n)
        else:
            logger.info(
                "Dry run: {:,} rows would be rewritten and {:,} FIPS restamped (pass --apply)",
                len(updates),
                len(res.restamp),
            )
    finally:
        conn.close()
        reader.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
