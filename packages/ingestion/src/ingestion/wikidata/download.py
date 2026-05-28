"""Wikidata jurisdiction enrichment downloader (FETCH layer).

Ported from packages/scrapers/src/scrapers/wikidata/load_jurisdictions_wikidata.py +
wikidata_integration.WikidataQuery to core_lib.http.BaseAsyncClient. This module
is download-only: it runs the live WDQS/SPARQL HTTP GET (``?query=...&format=json``)
and the Wikibase ``wbgetentities`` HTTP GET (``w/api.php``), shapes the responses
into per-jurisdiction enrichment rows, and writes them to
``data/cache/wikidata/<usps>/wikidata_enrichment_<type>.json`` with cache-freshness
reuse (same contract as ingestion.gsa.download).

The SEED (census bronze -> *_wikidata base rows) and the APPLY (UPDATE *_wikidata
from this cached enrichment, keyed on geoid) are TRANSFORMATIONS and live in dbt
(stg_wikidata__* + int_wikidata__jurisdictions_enriched), NOT here. See
ingestion/wikidata/__init__.py and dbt_project/models/staging/_schema_stg_wikidata.yml.

What this FETCH layer does NOT do (left in packages/scrapers/src/scrapers/wikidata/ and FLAGGED):
  * Postgres seeding / UPDATE / incremental-merge / coverage queries (-> dbt).
  * Census-literal -> Wikidata-QID *resolution* that needs the bronze GEOID list,
    fuzzy name matching (wbsearchentities entity-search), county-gap discovery,
    and checkpoint/resume. Those need a DB / fuzzy logic and stay as a scraper.
  * Pywikibot: the wbgetentities HTTP GET below covers the same JSON. The optional
    ``WIKIDATA_ENRICH_USE_PYWIKIBOT`` path is deferred (heavy SDK; not ported).

Usage:
    python -m ingestion.wikidata.download --states AL,GA --types county,city
    python -m ingestion.wikidata.download --states AL --force
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from loguru import logger

from core_lib.http import BaseAsyncClient, HttpClientConfig
from core_lib.logging import setup_logging


# ---------------------------------------------------------------------------
# Endpoints + cache config
# ---------------------------------------------------------------------------

# WDQS graph split (since 9 May 2025): civic/jurisdiction loaders use the *main*
# endpoint. Override with WIKIDATA_SPARQL_ENDPOINT or WIKIDATA_SPARQL_GRAPH.
_WDQS_MAIN = "https://query.wikidata.org/sparql"
_WDQS_SCHOLARLY = "https://query-scholarly.wikidata.org/sparql"
_WDQS_LEGACY_FULL = "https://query-legacy-full.wikidata.org/sparql"
_WIKIBASE_API = "https://www.wikidata.org/w/api.php"

CACHE_DIR = Path(os.getenv("WIKIDATA_CACHE_DIR", "data/cache/wikidata"))
_MAX_CACHE_AGE_S = int(os.getenv("WIKIDATA_CACHE_TTL_SECONDS", str(7 * 24 * 60 * 60)))
# WDQS POSTs long queries (SPARQL 1.1 protocol / proxy URL limits).
_SPARQL_MAX_GET_CHARS = max(512, int(os.getenv("WIKIDATA_SPARQL_MAX_GET_QUERY_CHARS", "6000") or "6000"))

_DEFAULT_UA = (
    "open-navigator-wikidata-loader/1.0 "
    "(https://github.com/; civic jurisdiction enrichment) httpx"
)


def _resolve_sparql_endpoint() -> str:
    override = (os.getenv("WIKIDATA_SPARQL_ENDPOINT") or "").strip()
    if override:
        return override
    graph = (os.getenv("WIKIDATA_SPARQL_GRAPH") or "main").strip().lower()
    if graph in ("scholarly", "scholar", "scholarly_graph", "cite", "wikicite"):
        return _WDQS_SCHOLARLY
    if graph in ("legacy_full", "legacy-full", "legacy", "full", "all"):
        return _WDQS_LEGACY_FULL
    return _WDQS_MAIN


# Minimal US-state map needed by the FETCH layer (USPS -> Wikidata Q-item +
# county-equivalent instance-of types). Mirrors STATE_MAP in the legacy script.
# Trimmed to what the bulk SPARQL queries need: q_code + county types.
STATE_MAP: dict[str, dict[str, Any]] = {
    "AL": {"name": "Alabama", "q_code": "Q173", "county_type": "Q13410400"},
    "AK": {"name": "Alaska", "q_code": "Q797", "county_instance_types": ["Q47168", "Q13410522", "Q56064719"]},
    "AZ": {"name": "Arizona", "q_code": "Q816"},
    "AR": {"name": "Arkansas", "q_code": "Q1612"},
    "CA": {"name": "California", "q_code": "Q99"},
    "CO": {"name": "Colorado", "q_code": "Q1261"},
    "CT": {"name": "Connecticut", "q_code": "Q779"},
    "DE": {"name": "Delaware", "q_code": "Q1393"},
    "DC": {"name": "District of Columbia", "q_code": "Q61"},
    "FL": {"name": "Florida", "q_code": "Q812"},
    "GA": {"name": "Georgia", "q_code": "Q1428", "county_type": "Q13410428"},
    "HI": {"name": "Hawaii", "q_code": "Q782"},
    "ID": {"name": "Idaho", "q_code": "Q1221"},
    "IL": {"name": "Illinois", "q_code": "Q1204"},
    "IN": {"name": "Indiana", "q_code": "Q1415", "county_type": "Q13414760"},
    "IA": {"name": "Iowa", "q_code": "Q1546"},
    "KS": {"name": "Kansas", "q_code": "Q1558"},
    "KY": {"name": "Kentucky", "q_code": "Q1603"},
    "LA": {"name": "Louisiana", "q_code": "Q1588"},
    "ME": {"name": "Maine", "q_code": "Q724"},
    "MD": {"name": "Maryland", "q_code": "Q1391"},
    "MA": {"name": "Massachusetts", "q_code": "Q771", "county_type": "Q13410485"},
    "MI": {"name": "Michigan", "q_code": "Q1166"},
    "MN": {"name": "Minnesota", "q_code": "Q1527"},
    "MS": {"name": "Mississippi", "q_code": "Q1494"},
    "MO": {"name": "Missouri", "q_code": "Q1581"},
    "MT": {"name": "Montana", "q_code": "Q1212"},
    "NE": {"name": "Nebraska", "q_code": "Q1553"},
    "NV": {"name": "Nevada", "q_code": "Q1227"},
    "NH": {"name": "New Hampshire", "q_code": "Q759"},
    "NJ": {"name": "New Jersey", "q_code": "Q1408"},
    "NM": {"name": "New Mexico", "q_code": "Q1522"},
    "NY": {"name": "New York", "q_code": "Q1384"},
    "NC": {"name": "North Carolina", "q_code": "Q1454"},
    "ND": {"name": "North Dakota", "q_code": "Q1207"},
    "OH": {"name": "Ohio", "q_code": "Q1397"},
    "OK": {"name": "Oklahoma", "q_code": "Q1649"},
    "OR": {"name": "Oregon", "q_code": "Q824"},
    "PA": {"name": "Pennsylvania", "q_code": "Q1400"},
    "PR": {"name": "Puerto Rico", "q_code": "Q1183", "county_instance_types": ["Q47168", "Q263639"]},
    "RI": {"name": "Rhode Island", "q_code": "Q1387"},
    "SC": {"name": "South Carolina", "q_code": "Q1456"},
    "SD": {"name": "South Dakota", "q_code": "Q1211"},
    "TN": {"name": "Tennessee", "q_code": "Q1509"},
    "TX": {"name": "Texas", "q_code": "Q1439"},
    "UT": {"name": "Utah", "q_code": "Q829"},
    "VT": {"name": "Vermont", "q_code": "Q16551"},
    "VA": {"name": "Virginia", "q_code": "Q1370"},
    "WA": {"name": "Washington", "q_code": "Q1223", "county_type": "Q13415369"},
    "WV": {"name": "West Virginia", "q_code": "Q1371"},
    "WI": {"name": "Wisconsin", "q_code": "Q1537", "county_type": "Q13414761"},
    "WY": {"name": "Wyoming", "q_code": "Q1214"},
}

PRIORITY_STATES = ["AL", "GA", "IN", "MA", "MT", "WA", "WI"]

# Jurisdiction types this FETCH layer can bulk-map per state via one WDQS query.
SUPPORTED_TYPES = ("county", "city", "school_district")


# ---------------------------------------------------------------------------
# SPARQL builders (one bulk WDQS query per state per type; in-process matching
# of identifiers is left to dbt / scripts, not done here).
# ---------------------------------------------------------------------------

def _county_type_values_clause(state_code: str) -> str:
    info = STATE_MAP.get(state_code) or {}
    instances = info.get("county_instance_types")
    if instances:
        return " ".join(f"wd:{q}" for q in instances)
    county_type_q = info.get("county_type")
    if county_type_q:
        return f"wd:{county_type_q} wd:Q47168"
    return "wd:Q47168"


def county_bulk_by_state_sparql(state_code: str, limit_rows: int = 600) -> str:
    sc = STATE_MAP[state_code]["q_code"]
    ctype = _county_type_values_clause(state_code)
    lim = max(50, min(2000, int(limit_rows)))
    return f"""
    SELECT DISTINCT ?item ?fips ?fipsAlt ?gnis WHERE {{
      VALUES ?countyType {{ {ctype} }}
      ?item wdt:P31 ?countyType .
      ?item wdt:P17 wd:Q30 .
      ?item wdt:P131 wd:{sc} .
      OPTIONAL {{ ?item wdt:P882 ?fips . }}
      OPTIONAL {{ ?item wdt:P3006 ?fipsAlt . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
    }}
    LIMIT {lim}
    """


def municipality_bulk_by_state_sparql(state_code: str, limit_rows: int = 8000) -> str:
    sc = STATE_MAP[state_code]["q_code"]
    lim = max(200, min(12000, int(limit_rows)))
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis WHERE {{
      ?item wdt:P131+ wd:{sc} .
      OPTIONAL {{ ?item wdt:P774 ?fips . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
    }}
    LIMIT {lim}
    """


def school_bulk_by_state_sparql(state_code: str, limit_rows: int = 2500) -> str:
    sc = STATE_MAP[state_code]["q_code"]
    lim = max(100, min(5000, int(limit_rows)))
    return f"""
    SELECT DISTINCT ?item ?fips ?gnis ?nces WHERE {{
      ?item wdt:P31 wd:Q1455778 .
      ?item wdt:P17 wd:Q30 .
      ?item wdt:P131+ wd:{sc} .
      OPTIONAL {{ ?item wdt:P882 ?fips . }}
      OPTIONAL {{ ?item wdt:P590 ?gnis . }}
      OPTIONAL {{ ?item wdt:P6545 ?nces . }}
    }}
    LIMIT {lim}
    """


_BULK_QUERY_BUILDERS = {
    "county": county_bulk_by_state_sparql,
    "city": municipality_bulk_by_state_sparql,
    "school_district": school_bulk_by_state_sparql,
}


# ---------------------------------------------------------------------------
# Wikibase claim -> WDQS-shaped row (ported from wikidata_wbget_claims.py so the
# FETCH layer is self-contained; same logical read path as Pywikibot ItemPage).
# ---------------------------------------------------------------------------

def _first_claim_sv(claims: Mapping[str, Any], pid: str) -> Any:
    c = claims.get(pid) if claims else None
    if not c:
        return None
    mainsnak = (c[0] or {}).get("mainsnak") or {}
    dv = mainsnak.get("datavalue")
    return None if dv is None else dv.get("value")


def _commons_thumb(fn: str | None) -> str | None:
    if not fn:
        return None
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{str(fn).replace(' ', '_')}"


def entity_to_enrichment_row(entity: Mapping[str, Any], qid: str) -> dict[str, Any]:
    """Map one ``wbgetentities`` blob into a flat enrichment record.

    The keys here are the join identifiers (fips/fips_alt/gnis/nces) plus the
    enrichment payload. The dbt apply layer joins to the *_wikidata seed on geoid
    after reconciling these identifiers; this layer does not own that join.
    """
    labels = entity.get("labels") or {}
    label = (labels.get("en") or {}).get("value") or ""
    if not label:
        for _lang, blob in sorted(labels.items()):
            if blob and blob.get("value"):
                label = blob["value"]
                break

    claims = entity.get("claims") or {}
    row: dict[str, Any] = {"wikidata_id": qid, "item_label": label}

    v = _first_claim_sv(claims, "P856")
    if isinstance(v, str):
        row["official_website"] = v
    v = _first_claim_sv(claims, "P1082")
    if isinstance(v, dict) and v.get("type") == "quantity":
        row["population"] = (v.get("amount") or "").lstrip("+")
    v = _first_claim_sv(claims, "P2046")
    if isinstance(v, dict) and v.get("type") == "quantity":
        row["area_sq_km"] = (v.get("amount") or "").lstrip("+")
    v = _first_claim_sv(claims, "P2013")
    if isinstance(v, str):
        row["facebook_username"] = v
    v = _first_claim_sv(claims, "P2002")
    if isinstance(v, str):
        row["twitter_username"] = v.strip().lstrip("@")
    v = _first_claim_sv(claims, "P2397")
    if isinstance(v, str):
        row["youtube_channel_id"] = v

    row["official_image_url"] = _commons_thumb(_first_claim_sv(claims, "P18"))
    row["locator_map_image"] = _commons_thumb(_first_claim_sv(claims, "P242"))
    row["page_banner_image"] = _commons_thumb(_first_claim_sv(claims, "P948"))

    coord = _first_claim_sv(claims, "P625")
    if isinstance(coord, dict) and coord.get("type") == "globecoordinate":
        row["latitude"] = str(coord["latitude"])
        row["longitude"] = str(coord["longitude"])

    for pid in ("P774", "P882"):
        raw = _first_claim_sv(claims, pid)
        if isinstance(raw, str):
            row["fips_code"] = raw.replace("-", "")
            break
    fal = _first_claim_sv(claims, "P3006")
    if isinstance(fal, str):
        row["fips_alt"] = fal.replace("-", "")
    gv = _first_claim_sv(claims, "P590")
    if isinstance(gv, str):
        row["gnis_id"] = gv.replace("-", "")
    nv = _first_claim_sv(claims, "P6545")
    if isinstance(nv, str):
        row["nces_id"] = nv.replace("-", "")

    pc = _first_claim_sv(claims, "P281")
    if isinstance(pc, str):
        row["postal_code"] = pc
    am = _first_claim_sv(claims, "P3529")
    if isinstance(am, dict) and am.get("type") == "quantity":
        row["per_capita_income"] = (am.get("amount") or "").lstrip("+")
    hh = _first_claim_sv(claims, "P1538")
    if isinstance(hh, dict) and hh.get("type") == "quantity":
        row["number_of_households"] = (hh.get("amount") or "").lstrip("+")
    ma = _first_claim_sv(claims, "P1310")
    if isinstance(ma, dict) and ma.get("type") == "quantity":
        row["median_age"] = (ma.get("amount") or "").lstrip("+")
    return row


def _qid_from_item_uri(item_uri: str | None) -> str | None:
    if not item_uri:
        return None
    qid = str(item_uri).rsplit("/", 1)[-1].strip()
    return qid if qid.startswith("Q") else None


# ---------------------------------------------------------------------------
# HTTP client (BaseAsyncClient subclass)
# ---------------------------------------------------------------------------

class WikidataClient(BaseAsyncClient):
    """BaseAsyncClient for WDQS SPARQL + Wikibase ``wbgetentities`` HTTP GET.

    WDQS is easily overloaded; the rate limiter + retry-on-429/5xx of
    BaseAsyncClient cover the core throttling. The legacy WikidataQuery's bespoke
    rolling-budget / cooldown / UA-rotation guards are intentionally NOT ported —
    they are operational tuning, not part of the fetch contract. Set
    ``WIKIDATA_THROTTLE_RATE_PER_SEC`` lower for very large full-US runs.
    """

    def __init__(self) -> None:
        self._sparql_endpoint = _resolve_sparql_endpoint()
        try:
            rate = float(os.getenv("WIKIDATA_THROTTLE_RATE_PER_SEC", "0.5") or "0.5")
        except ValueError:
            rate = 0.5
        try:
            timeout = float(os.getenv("WIKIDATA_SPARQL_TIMEOUT_SECONDS", "180") or "180")
        except ValueError:
            timeout = 180.0
        super().__init__(
            HttpClientConfig(
                # base_url is the wikidata.org host; WDQS is a different host, so
                # SPARQL requests pass the absolute endpoint URL.
                base_url="https://www.wikidata.org",
                source="wikidata",
                timeout_s=timeout,
                rate_limit_per_sec=rate if rate > 0 else None,
                rate_limit_burst=1,
                default_headers={
                    "User-Agent": os.getenv("WIKIDATA_USER_AGENT", "").strip() or _DEFAULT_UA,
                    "Accept": "application/sparql-results+json",
                },
            )
        )

    async def execute_sparql(self, query: str) -> list[dict[str, Any]]:
        """Run a WDQS SELECT; return list of {var: value} binding dicts."""
        if len(query) > _SPARQL_MAX_GET_CHARS:
            resp = await self.post(
                self._sparql_endpoint,
                data={"query": query, "format": "json"},
            )
        else:
            resp = await self.get(
                self._sparql_endpoint,
                params={"query": query, "format": "json"},
            )
        data = resp.json()
        bindings = data.get("results", {}).get("bindings", [])
        out: list[dict[str, Any]] = []
        for binding in bindings:
            out.append({k: v.get("value") for k, v in binding.items()})
        return out

    async def wikibase_get_entities(
        self, entity_ids: Iterable[str], *, props: str = "labels|claims"
    ) -> dict[str, Any]:
        """Read claims for Q-ids via ``wbgetentities`` (chunked by 50)."""
        ids = [e for e in entity_ids if str(e).startswith("Q")]
        merged: dict[str, Any] = {}
        for ci in range(0, len(ids), 50):
            ids_pipe = "|".join(ids[ci : ci + 50])
            resp = await self.get(
                _WIKIBASE_API,
                params={
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": ids_pipe,
                    "props": props,
                    "languages": "en",
                },
                headers={"Accept": "application/json"},
            )
            ents = resp.json().get("entities") or {}
            merged.update({k: v for k, v in ents.items() if str(k).startswith("Q")})
        return merged


# ---------------------------------------------------------------------------
# Download orchestration + cache freshness (mirrors ingestion.gsa.download)
# ---------------------------------------------------------------------------

def _cache_path(state_code: str, jurisdiction_type: str) -> Path:
    return CACHE_DIR / state_code.upper() / f"wikidata_enrichment_{jurisdiction_type}.json"


def _is_fresh(path: Path) -> bool:
    return path.exists() and (datetime.now().timestamp() - path.stat().st_mtime) < _MAX_CACHE_AGE_S


async def _fetch_type_enrichment(
    client: WikidataClient, state_code: str, jurisdiction_type: str, *, hydrate_props: str
) -> list[dict[str, Any]]:
    """One bulk WDQS map query for the state+type, then wbgetentities hydration."""
    builder = _BULK_QUERY_BUILDERS[jurisdiction_type]
    bindings = await client.execute_sparql(builder(state_code))
    qids: list[str] = []
    seen: set[str] = set()
    for b in bindings:
        qid = _qid_from_item_uri(b.get("item"))
        if qid and qid not in seen:
            seen.add(qid)
            qids.append(qid)
    if not qids:
        return []
    entities = await client.wikibase_get_entities(qids, props=hydrate_props)
    rows: list[dict[str, Any]] = []
    for qid, entity in entities.items():
        if isinstance(entity, dict) and entity.get("missing"):
            continue
        row = entity_to_enrichment_row(entity, qid)
        row["jurisdiction_type"] = jurisdiction_type
        row["state_code"] = state_code.upper()
        rows.append(row)
    return rows


async def download_state_enrichment(
    state_code: str,
    jurisdiction_types: Iterable[str],
    *,
    force: bool = False,
    client: WikidataClient | None = None,
) -> dict[str, Path]:
    """Fetch + cache Wikidata enrichment JSON for one state, per type.

    Returns {jurisdiction_type: cache_path}. Reuses a <TTL cache unless force.
    """
    us = state_code.upper()
    if us not in STATE_MAP:
        raise ValueError(f"Unknown USPS code: {state_code!r} (not in STATE_MAP)")
    types = [t for t in jurisdiction_types if t in SUPPORTED_TYPES]
    bound = logger.bind(source="wikidata", state=us)
    out: dict[str, Path] = {}

    owns_client = client is None
    if owns_client:
        client = WikidataClient()
        await client.__aenter__()
    try:
        for jtype in types:
            path = _cache_path(us, jtype)
            if not force and _is_fresh(path):
                bound.info(f"cache_hit {path}")
                out[jtype] = path
                continue
            # State descriptive metadata (aliases, demonym, etc.) needs more props.
            props = "labels|claims"
            rows = await _fetch_type_enrichment(client, us, jtype, hydrate_props=props)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "source": "wikidata",
                "state_code": us,
                "jurisdiction_type": jtype,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "endpoint": client._sparql_endpoint,
                "rows": rows,
            }
            path.write_text(json.dumps(payload, indent=2, default=str))
            bound.info(f"downloaded {len(rows)} {jtype} enrichment row(s) -> {path}")
            out[jtype] = path
    finally:
        if owns_client:
            await client.__aexit__(None, None, None)
    return out


async def download(
    states: Iterable[str], jurisdiction_types: Iterable[str], *, force: bool = False
) -> dict[str, dict[str, Path]]:
    types = list(jurisdiction_types)
    out: dict[str, dict[str, Path]] = {}
    async with WikidataClient() as client:
        for state in states:
            out[state.upper()] = await download_state_enrichment(
                state, types, force=force, client=client
            )
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download Wikidata jurisdiction enrichment JSON into data/cache/wikidata/"
    )
    parser.add_argument(
        "--states",
        type=str,
        default=",".join(PRIORITY_STATES),
        help=f"Comma-separated USPS codes (default: priority states {','.join(PRIORITY_STATES)})",
    )
    parser.add_argument(
        "--all-us-states",
        action="store_true",
        help="Fetch every USPS code in STATE_MAP (50 states + DC + PR)",
    )
    parser.add_argument(
        "--types",
        type=str,
        default=",".join(SUPPORTED_TYPES),
        help=f"Comma-separated jurisdiction types (default: {','.join(SUPPORTED_TYPES)})",
    )
    parser.add_argument("--force", action="store_true", help="Re-download even if a fresh cache exists")
    return parser


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    if args.all_us_states:
        states = sorted(STATE_MAP.keys())
    else:
        states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    types = [t.strip().lower() for t in args.types.split(",") if t.strip()]
    unknown = [s for s in states if s not in STATE_MAP]
    if unknown:
        raise SystemExit(f"Unknown USPS code(s): {', '.join(unknown)}")
    result = asyncio.run(download(states, types, force=args.force))
    total = sum(len(v) for v in result.values())
    logger.info(f"wikidata enrichment cache written for {len(result)} state(s), {total} file(s)")


if __name__ == "__main__":
    main()
