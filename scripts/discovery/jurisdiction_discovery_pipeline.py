"""
Jurisdiction discovery pipeline (merged)

Combines:
- **Postgres bronze** inputs: ``bronze.bronze_jurisdictions_{states,municipalities,counties,school_districts}``
- **Homepage seeds** from dbt ``intermediate.int_jurisdiction_websites`` only (GSA/USCM/NCES/NACO union
  built in the warehouse). No pattern-guessed ``.gov`` URLs and no Wikidata **website** backfill.
- **Deep discovery** from ``ComprehensiveDiscoveryPipeline``: crawl that seed URL for YouTube, social,
  meeting platforms, agenda links, etc. (derived links are from scraping the allowed homepage.)

Writes discovered metadata to **new** tables (suffix ``_scraped``), not Delta Lake.
Each completed jurisdiction is **upserted to Postgres immediately** (no waiting for a large batch).
**DDL runs automatically** from ``scripts/discovery/sql/bronze_jurisdictions_scraped.sql`` (no separate
``psql`` step). Neon deploys may still apply ``009_create_bronze_jurisdictions_scraped.sql`` (same DDL).

Resolves DB URL from ``.env`` / env (``OPEN_NAVIGATOR_DATABASE_URL``, ``NEON_*``, ``DATABASE_URL``),
then falls back to local Postgres (see ``scripts.database.target_database_url``).

Usage:
  .venv/bin/python -m scripts.discovery.jurisdiction_discovery_pipeline --state AL
  .venv/bin/python -m scripts.discovery.jurisdiction_discovery_pipeline --state AL --include-states
  .venv/bin/python -m scripts.discovery.jurisdiction_discovery_pipeline --state AL --gsa-bulk-only
  .venv/bin/python -m scripts.discovery.jurisdiction_discovery_pipeline --state AL --truncate-scraped --no-incremental
  # (--gsa-bulk-only: bulk upsert using int_jurisdiction_websites only; name kept for CLI compatibility)
  ./scripts/discovery/run_jurisdiction_discovery.sh --state AL --gsa-bulk-only
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger
from tqdm.asyncio import tqdm

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    import psycopg2
    from psycopg2.extras import Json, execute_batch
except ModuleNotFoundError as exc:
    if exc.name != "psycopg2":
        raise
    psycopg2 = None  # type: ignore[misc,assignment]

from scripts.discovery.comprehensive_discovery_pipeline import ComprehensiveDiscoveryPipeline


def _load_repo_dotenv() -> None:
    """Load ``<repo>/.env`` so ``DATABASE_URL`` / Neon vars work when running ``python -m ...``."""
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(_root / ".env")


def resolve_database_url() -> str:
    _load_repo_dotenv()
    url = (
        os.getenv("OPEN_NAVIGATOR_DATABASE_URL", "").strip()
        or os.getenv("NEON_DATABASE_URL_DEV", "").strip()
        or os.getenv("NEON_DATABASE_URL", "").strip()
        or os.getenv("DATABASE_URL", "").strip()
    )
    if url:
        return url
    from scripts.database.target_database_url import resolve_target_database_url

    return resolve_target_database_url()


SCRAPED_TABLE: Dict[str, str] = {
    "state": "bronze.bronze_jurisdictions_states_scraped",
    "city": "bronze.bronze_jurisdictions_municipalities_scraped",
    "municipality": "bronze.bronze_jurisdictions_municipalities_scraped",
    "county": "bronze.bronze_jurisdictions_counties_scraped",
    "school_district": "bronze.bronze_jurisdictions_school_districts_scraped",
}

# dbt intermediate model (``dbt run --select int_jurisdiction_websites``)
INT_JURISDICTION_WEBSITES_TABLE = "intermediate.int_jurisdiction_websites"

# SQL fragment for ``ORDER BY`` / ``MIN()`` when picking among multiple URLs per ``jurisdiction_id``.
# Counties: NACO (association-maintained county site) before GSA — reduces bad GSA stem/name matches
# on .gov domains. Other types: keep GSA first (authoritative .gov registry).
WEBSITE_SOURCE_PRIORITY_ORDER_SQL = (
    "CASE WHEN jurisdiction_id LIKE 'county_%' THEN "
    "CASE website_source WHEN 'naco' THEN 1 WHEN 'gsa' THEN 2 WHEN 'uscm' THEN 3 "
    "WHEN 'nces_directory' THEN 4 ELSE 5 END ELSE "
    "CASE website_source WHEN 'gsa' THEN 1 WHEN 'uscm' THEN 2 WHEN 'nces_directory' THEN 3 "
    "WHEN 'naco' THEN 4 ELSE 5 END END"
)

_SCRAPED_DDL_PATH = Path(__file__).resolve().parent / "sql" / "bronze_jurisdictions_scraped.sql"


def scraped_jurisdictions_ddl_path() -> Path:
    """Path to the single bundled CREATE TABLE script (Neon 009 mirrors this)."""
    return _SCRAPED_DDL_PATH


def normalize_gov_host(value: str) -> str:
    """
    Canonical host for matching GSA ``domain_name`` to generated candidates.

    Strips scheme, ``www.``, path, port, and trailing dots so ``WWW.FOO.GOV/``
    and ``foo.gov`` both match ``foo.gov``.
    """
    v = (value or "").strip().lower()
    if v.startswith("http://"):
        v = v[7:]
    if v.startswith("https://"):
        v = v[8:]
    v = v.split("/")[0].split("@")[-1].split(":")[0]
    if v.startswith("www."):
        v = v[4:]
    return v.rstrip(".")


def ensure_scraped_tables(conn) -> None:
    """Create ``bronze.*_scraped`` tables if missing (idempotent)."""
    p = _SCRAPED_DDL_PATH
    if not p.is_file():
        raise FileNotFoundError(
            f"Missing DDL file: {p} — restore scripts/discovery/sql/bronze_jurisdictions_scraped.sql"
        )
    sql = p.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    logger.info(f"Ensured bronze *_scraped tables from {p.name}")


def clean_scraped_tables(conn, *, state_filter: Optional[str] = None) -> None:
    """
    Remove rows from ``bronze.*_scraped`` before a discovery run.

    - ``state_filter`` = 2-letter USPS: ``DELETE`` only those rows in each scraped table.
    - ``state_filter`` = ``None``: ``TRUNCATE`` all four ``*_scraped`` tables (every state).
    """
    tables = sorted(set(SCRAPED_TABLE.values()))
    with conn.cursor() as cur:
        if state_filter:
            st = state_filter.strip().upper()
            if len(st) != 2:
                raise ValueError(f"state_filter must be 2-letter USPS, got {state_filter!r}")
            deleted = 0
            for tbl in tables:
                cur.execute(
                    f"DELETE FROM {tbl} WHERE upper(btrim(usps::text)) = %s",
                    (st,),
                )
                deleted += cur.rowcount
            conn.commit()
            logger.warning(
                "Removed {:,} scraped row(s) across {} table(s) for state {}",
                deleted,
                len(tables),
                st,
            )
        else:
            cur.execute("TRUNCATE TABLE " + ", ".join(tables))
            conn.commit()
            logger.warning("Truncated ALL rows in bronze *_scraped tables: {}", tables)


def load_gsa_domain_set(conn) -> Set[str]:
    """Normalized registrable hosts from ``bronze.bronze_gov_domains`` (see ``normalize_gov_host``)."""
    domains: Set[str] = set()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT trim(domain_name)
            FROM bronze.bronze_gov_domains
            WHERE domain_name IS NOT NULL AND btrim(domain_name) <> ''
            """
        )
        for (d,) in cur.fetchall():
            h = normalize_gov_host(d or "")
            if h:
                domains.add(h)
    logger.info(f"Loaded {len(domains):,} GSA .gov hosts (normalized) from bronze.bronze_gov_domains")
    return domains


def load_gsa_city_state_domain_map(conn) -> Dict[Tuple[str, str], str]:
    """
    Map ``(USPS, cleaned_city_key)`` → normalized host when GSA rows include ``city`` + ``state``.

    Used when hostname heuristics (``candidate_gov_domains``) do not match the registered
    ``domain_name`` (e.g. uncommon naming), but ``city``/``state`` align with Census place rows.
    """
    out: Dict[Tuple[str, str], str] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT upper(trim(state)), lower(trim(city)), min(trim(domain_name))
            FROM bronze.bronze_gov_domains
            WHERE state IS NOT NULL
              AND btrim(state) <> ''
              AND city IS NOT NULL
              AND btrim(city) <> ''
              AND domain_name IS NOT NULL
              AND btrim(domain_name) <> ''
            GROUP BY 1, 2
            """
        )
        for st_raw, city_raw, dom_raw in cur.fetchall():
            st = (st_raw or "").strip().upper()
            if len(st) != 2:
                continue
            city_key = _clean_place_name(city_raw or "").lower().strip()
            host = normalize_gov_host(dom_raw or "")
            if not city_key or not host:
                continue
            k = (st, city_key)
            if k not in out:
                out[k] = host
    logger.info(f"Loaded {len(out):,} GSA city/state → host keys from bronze.bronze_gov_domains")
    return out


def jurisdiction_pk_from_geoid(geoid: Optional[str], jtype: Optional[str]) -> str:
    """
    Primary key matching ``int_jurisdictions.jurisdiction_id`` (``{type}_{padded_geoid}``).

    Aligns with dbt ``int_jurisdictions`` padding: county 5, municipality/school 7, township 10, state 2.
    """
    raw = str(geoid or "").strip().replace("-", "")
    if not raw or not raw.isdigit():
        return ""
    jt = (jtype or "city").lower()
    if jt == "state":
        return f"state_{raw.zfill(2)}"
    if jt == "county":
        return f"county_{raw.zfill(5)}"
    if jt in ("school_district", "school"):
        return f"school_district_{raw.zfill(7)}"
    if jt == "township":
        return f"township_{raw.zfill(10)}"
    # city / municipality / place
    return f"municipality_{raw.zfill(7)}"


def load_int_jurisdiction_website_map(conn) -> Dict[str, str]:
    """
    ``jurisdiction_id`` → canonical ``website_url`` from ``intermediate.int_jurisdiction_websites``.

    One URL per jurisdiction (prefers GSA .gov registry, then USCM, NCES directory, then NACo).
    """
    out: Dict[str, str] = {}
    sql = f"""
        SELECT DISTINCT ON (jurisdiction_id)
            jurisdiction_id,
            trim(website_url) AS website_url
        FROM {INT_JURISDICTION_WEBSITES_TABLE}
        WHERE jurisdiction_id IS NOT NULL
          AND website_url IS NOT NULL
          AND btrim(website_url) <> ''
        ORDER BY jurisdiction_id,
            ({WEBSITE_SOURCE_PRIORITY_ORDER_SQL}),
            website_record_key
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        for jid, url in cur.fetchall():
            key = str(jid or "").strip()
            val = str(url or "").strip()
            if key and val:
                out[key] = val
    logger.info(
        "Loaded {:,} jurisdiction_id → website_url row(s) from {}",
        len(out),
        INT_JURISDICTION_WEBSITES_TABLE,
    )
    return out


def match_jurisdiction_to_gsa_host(
    name: str,
    state_code: str,
    jtype: str,
    gsa_hosts: Set[str],
    city_state_hosts: Dict[Tuple[str, str], str],
) -> Optional[str]:
    """Return normalized host if either heuristic candidates or city/state map hits GSA."""
    st = (state_code or "").strip().upper()
    jt = (jtype or "city").lower()
    for host in candidate_gov_domains(name, state_code, jt):
        nh = normalize_gov_host(host)
        if nh and nh in gsa_hosts:
            return nh
    ck = _clean_place_name(name or "").lower().strip()
    if ck and len(st) == 2:
        h = city_state_hosts.get((st, ck))
        if h:
            return h
    return None


def _clean_place_name(name: str) -> str:
    clean_name = (name or "").strip()
    for suffix in [
        " city",
        " town",
        " village",
        " borough",
        " CDP",
        " County",
        " municipality",
        " City",
        " Town",
        " Village",
        " Borough",
        " COUNTY",
    ]:
        clean_name = clean_name.replace(suffix, "")
    return clean_name


def candidate_gov_domains(name: str, state_code: str, jtype: str) -> List[str]:
    """Ordered .gov host candidates (no scheme), matching legacy discovery_pipeline patterns."""
    if not name or not state_code:
        return []
    state_code = state_code.strip().upper()
    clean_name = _clean_place_name(name)
    if jtype == "county":
        clean_name = clean_name.replace("County", "").replace("county", "").strip()

    base_name = clean_name.lower().strip()
    compact_name = base_name.replace(" ", "").replace(".", "").replace(",", "").replace("'", "")
    hyphenated_name = base_name.replace(" ", "-").replace(".", "").replace(",", "").replace("'", "")
    state_lower = state_code.lower()

    # US state portals: USPS 2-letter host is the dominant pattern (e.g. in.gov, alabama.gov).
    if jtype == "state":
        return [
            f"{state_lower}.gov",
            f"www.{state_lower}.gov",
            f"portal.{state_lower}.gov",
            f"{compact_name}.gov",
            f"www.{compact_name}.gov",
            f"{compact_name}{state_lower}.gov",
            f"{hyphenated_name}.gov",
            f"www.{hyphenated_name}.gov",
        ]

    candidates = [
        f"{compact_name}{state_lower}.gov",
        f"{compact_name}-{state_lower}.gov",
        f"{state_lower}{compact_name}.gov",
        f"{hyphenated_name}{state_lower}.gov",
        f"{hyphenated_name}-{state_lower}.gov",
        f"{compact_name}.gov",
        f"{hyphenated_name}.gov",
        f"cityof{compact_name}.gov",
        f"{compact_name}city.gov",
        f"{compact_name}county.gov",
        f"{compact_name}county{state_lower}.gov",
    ]
    if jtype == "county":
        candidates.extend(
            [
                f"{compact_name}co.gov",
                f"co{compact_name}{state_lower}.gov",
            ]
        )
    return candidates


def load_jurisdictions_from_postgres(
    conn,
    *,
    state_filter: Optional[str] = None,
    top_n: Optional[int] = None,
    include_states: bool = False,
    include_municipalities: bool = True,
    include_counties: bool = True,
    include_schools: bool = False,
) -> List[Dict[str, Any]]:
    """
    Build jurisdiction dicts compatible with ``ComprehensiveDiscoveryPipeline.discover_jurisdiction``.
    """
    out: List[Dict[str, Any]] = []
    usps = state_filter.strip().upper() if state_filter else None
    lim = int(top_n) if top_n is not None and top_n > 0 else None

    def _maybe_limit(sql: str) -> Tuple[str, list]:
        args: list = []
        if usps:
            sql += " AND usps = %s"
            args.append(usps)
        sql += " ORDER BY geoid"
        if lim is not None:
            sql += " LIMIT %s"
            args.append(lim)
        return sql, args

    with conn.cursor() as cur:
        if include_states:
            sql, args = _maybe_limit(
                """
                SELECT geoid, usps, name, ansicode
                FROM bronze.bronze_jurisdictions_states
                WHERE 1=1
                """
            )
            cur.execute(sql, args)
            for geoid, usps_r, name, ansi in cur.fetchall():
                gid = str(geoid or "").strip().replace("-", "")
                st = str(usps_r or "").strip().upper()
                if not gid or not st:
                    continue
                out.append(
                    {
                        "GEOID": gid,
                        "name": str(name or "").strip(),
                        "state_code": st,
                        "type": "state",
                        "population": 0,
                        "ANSICODE": str(ansi).strip() if ansi else "",
                        "full_name": str(name or "").strip(),
                    }
                )
        if include_municipalities:
            sql, args = _maybe_limit(
                """
                SELECT geoid, usps, name, ansicode
                FROM bronze.bronze_jurisdictions_municipalities
                WHERE 1=1
                """
            )
            cur.execute(sql, args)
            for geoid, usps_r, name, ansi in cur.fetchall():
                gid = str(geoid or "").strip().replace("-", "")
                if not gid:
                    continue
                out.append(
                    {
                        "GEOID": gid,
                        "name": str(name or "").strip(),
                        "state_code": str(usps_r or "").strip().upper(),
                        "type": "city",
                        "population": 0,
                        "ANSICODE": str(ansi).strip() if ansi else "",
                        "full_name": str(name or "").strip(),
                    }
                )
        if include_counties:
            sql, args = _maybe_limit(
                """
                SELECT geoid, usps, name, ansicode
                FROM bronze.bronze_jurisdictions_counties
                WHERE 1=1
                """
            )
            cur.execute(sql, args)
            for geoid, usps_r, name, ansi in cur.fetchall():
                gid = str(geoid or "").strip().replace("-", "")
                if not gid:
                    continue
                out.append(
                    {
                        "GEOID": gid,
                        "name": str(name or "").strip(),
                        "state_code": str(usps_r or "").strip().upper(),
                        "type": "county",
                        "population": 0,
                        "ANSICODE": str(ansi).strip() if ansi else "",
                        "full_name": str(name or "").strip(),
                    }
                )
        if include_schools:
            sql, args = _maybe_limit(
                """
                SELECT geoid, usps, name
                FROM bronze.bronze_jurisdictions_school_districts
                WHERE 1=1
                """
            )
            cur.execute(sql, args)
            for geoid, usps_r, name in cur.fetchall():
                gid = str(geoid or "").strip().replace("-", "")
                if not gid:
                    continue
                out.append(
                    {
                        "GEOID": gid,
                        "name": str(name or "").strip(),
                        "state_code": str(usps_r or "").strip().upper(),
                        "type": "school_district",
                        "population": 0,
                        "ANSICODE": "",
                        "full_name": str(name or "").strip(),
                    }
                )
    logger.info(f"Loaded {len(out):,} jurisdiction row(s) from Postgres bronze")
    return out


def _scraped_table_for(jtype: str) -> str:
    key = (jtype or "city").lower()
    return SCRAPED_TABLE.get(key, SCRAPED_TABLE["city"])


def _result_to_scraped_row(r: Dict[str, Any]) -> Tuple[str, str, str, Optional[str], Optional[str], Optional[str], str, str, float, Dict[str, Any]]:
    j = r.get("jurisdiction") or {}
    geoid = str(
        r.get("jurisdiction_id")
        or j.get("GEOID")
        or j.get("geoid")
        or j.get("Geoid")
        or ""
    ).strip()
    usps = str(j.get("state_code") or j.get("USPS") or "").strip().upper()
    jtype = (j.get("type") or "city").lower()
    websites = r.get("websites") or []
    homepage_url = websites[0]["url"] if websites else None
    homepage_final = websites[0].get("final_url") if websites else None
    payload = {
        "websites": r.get("websites"),
        "youtube_channels": r.get("youtube_channels"),
        # Per-URL probe audit: outcome not_found | found | error | skipped_invalid_url | timeout; checked_at UTC ISO
        "youtube_channel_checks": r.get("youtube_channel_checks"),
        "other_video": r.get("other_video"),
        "meeting_platforms": r.get("meeting_platforms"),
        "social_media": r.get("social_media"),
        "agenda_portals": r.get("agenda_portals"),
        "jurisdiction": j,
        "discovery_timestamp": r.get("discovery_timestamp"),
        "error": r.get("error"),
    }
    gsa_dom = None
    for w in websites:
        dm = (w or {}).get("discovery_method")
        if dm in ("gsa_match", "int_jurisdiction_websites"):
            gsa_dom = (w.get("url") or "").replace("https://", "").replace("http://", "").split("/")[0].lower()
            break
    return (
        geoid,
        usps,
        jtype,
        homepage_url,
        homepage_final,
        gsa_dom,
        "deep_scrape",
        str(r.get("status") or "unknown"),
        float(r.get("completeness_score") or 0.0),
        payload,
    )


class JurisdictionDiscoveryPipeline(ComprehensiveDiscoveryPipeline):
    """
    Postgres-backed discovery: read bronze jurisdiction rows, seed homepages from
    ``intermediate.int_jurisdiction_websites``, run async deep discovery from that URL,
    upsert into ``*_scraped`` tables.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        youtube_api_key: Optional[str] = None,
        max_concurrent: int = 10,
        incremental: bool = True,
        refresh_days: int = 90,
        write_parquet_backup: bool = False,
        wikidata_enabled: bool = False,
    ):
        self.database_url = database_url or resolve_database_url()
        self.write_parquet_backup = write_parquet_backup
        self.wikidata_enabled = bool(wikidata_enabled)
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for JurisdictionDiscoveryPipeline")
        self._pg: Optional[Any] = None
        self._ijw_by_jurisdiction_id: Optional[Dict[str, str]] = None
        self._discovery_context: Optional[Dict[str, Any]] = None
        super().__init__(
            youtube_api_key=youtube_api_key,
            max_concurrent=max_concurrent,
            output_dir="data/bronze/discovered_sources",
            gold_output_dir="data/gold",
            incremental=incremental,
            refresh_days=refresh_days,
            enable_wikidata=self.wikidata_enabled,
        )

    def _conn(self):
        if self._pg is None:
            self._pg = psycopg2.connect(self.database_url)
        return self._pg

    def close(self) -> None:
        if self._pg is not None:
            self._pg.close()
            self._pg = None
        self._ijw_by_jurisdiction_id = None

    def _ensure_int_jurisdiction_websites_cache(self) -> None:
        if self._ijw_by_jurisdiction_id is not None:
            return
        conn = self._conn()
        self._ijw_by_jurisdiction_id = load_int_jurisdiction_website_map(conn)

    def _seed_website_from_int_table(self, jurisdiction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._ensure_int_jurisdiction_websites_cache()
        assert self._ijw_by_jurisdiction_id is not None
        pk = jurisdiction_pk_from_geoid(
            str(jurisdiction.get("GEOID") or ""),
            str(jurisdiction.get("type") or "city"),
        )
        if not pk:
            return None
        url = self._ijw_by_jurisdiction_id.get(pk)
        if not url:
            return None
        u = url.strip()
        if not u.lower().startswith(("http://", "https://")):
            u = f"https://{u.lstrip('/')}"
        return {"url": u, "final_url": u, "status": "active", "discovery_method": "int_jurisdiction_websites"}

    async def _discover_website(self, name: str, state: str, jtype: str) -> Optional[Dict[str, Any]]:
        """Use dbt ``int_jurisdiction_websites`` only — no pattern-probed .com/.gov guesses."""
        del name, state  # context carries GEOID + type
        j = self._discovery_context or {}
        return self._seed_website_from_int_table(j)

    async def _enrich_with_wikidata(self, results: Dict[str, Any], name: str, state: str, jtype: str) -> None:
        """Keep YouTube/social from Wikidata; never add a primary **website** from Wikidata."""
        if not self.wikidata_enabled:
            return
        await super()._enrich_with_wikidata(results, name, state, jtype)
        results["websites"] = [
            w
            for w in (results.get("websites") or [])
            if (w or {}).get("discovery_method") != "wikidata"
        ]
        if not results["websites"] and results.get("status") == "success":
            results["status"] = "partial"

    async def discover_jurisdiction(self, jurisdiction: Dict[str, Any]) -> Dict[str, Any]:
        self._discovery_context = jurisdiction
        try:
            result = await super().discover_jurisdiction(jurisdiction)
            if not result.get("websites"):
                hint = self._seed_website_from_int_table(jurisdiction)
                if hint:
                    result["websites"] = [hint]
                    if result.get("status") == "partial":
                        result["status"] = "success"
                    result["completeness_score"] = self._calculate_completeness(result)
            return result
        finally:
            self._discovery_context = None

    async def discover_batch(self, jurisdictions: List[Dict[str, Any]], save_interval: int = 100) -> List[Dict[str, Any]]:
        """
        Run discovery and **commit each row to bronze ``*_scraped`` as soon as that jurisdiction finishes**.

        ``save_interval`` is ignored for Postgres (kept for API compatibility). If
        ``write_parquet_backup`` is true, a single legacy JSON/CSV/parquet export runs at the end.
        """
        self._ensure_int_jurisdiction_websites_cache()
        results: List[Dict[str, Any]] = []
        n = len(jurisdictions)
        logger.info(f"Starting batch discovery for {n} jurisdictions (per-row Postgres upsert)")
        tasks = [self._discover_jurisdiction_safe(j) for j in jurisdictions]
        try:
            for i, task in enumerate(tqdm.as_completed(tasks, total=n)):
                result = await task
                self._save_results([result], f"live_{i + 1}")
                results.append(result)
                if self.write_parquet_backup and save_interval > 0 and (i + 1) % save_interval == 0:
                    super()._save_results(results, f"batch_{i + 1}")
        except BaseException:
            logger.warning(
                "Batch stopped after {} jurisdiction(s); {} row(s) already committed to *_scraped",
                len(results),
                len(results),
            )
            raise
        if self.write_parquet_backup and results:
            super()._save_results(results, "final")
        return results

    def __enter__(self) -> "JurisdictionDiscoveryPipeline":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _load_existing_scraped_ids(self) -> Dict[str, Dict[str, Any]]:
        """geoid -> {is_stale, age_days} from *_scraped for incremental mode."""
        if not self.incremental:
            return {}
        conn = self._conn()
        discoveries: Dict[str, Dict[str, Any]] = {}
        q = """
            SELECT geoid, discovered_at::text FROM {tbl}
        """
        with conn.cursor() as cur:
            for tbl in sorted(set(SCRAPED_TABLE.values())):
                cur.execute(q.format(tbl=tbl))
                for geoid, ts in cur.fetchall():
                    gid = str(geoid or "").strip()
                    if not gid:
                        continue
                    try:
                        raw = str(ts).strip()
                        discovery_date = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        if discovery_date.tzinfo is not None:
                            discovery_date = discovery_date.astimezone(timezone.utc).replace(tzinfo=None)
                        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
                        age_days = (now_naive - discovery_date).days
                    except Exception:
                        age_days = self.refresh_days + 1
                    is_stale = age_days > self.refresh_days
                    discoveries[gid] = {"is_stale": is_stale, "age_days": age_days}
        logger.info(f"Incremental: {len(discoveries):,} geoid(s) already in *_scraped")
        return discoveries

    def load_jurisdictions(
        self,
        state_filter: Optional[str] = None,
        top_n: Optional[int] = None,
        *,
        include_states: bool = False,
        include_municipalities: bool = True,
        include_counties: bool = True,
        include_schools: bool = False,
    ) -> List[Dict[str, Any]]:
        conn = self._conn()
        jurisdictions = load_jurisdictions_from_postgres(
            conn,
            state_filter=state_filter,
            top_n=top_n,
            include_states=include_states,
            include_municipalities=include_municipalities,
            include_counties=include_counties,
            include_schools=include_schools,
        )
        scraped_index = self._load_existing_scraped_ids()
        if scraped_index:
            before = len(jurisdictions)
            jurisdictions = [
                j
                for j in jurisdictions
                if j.get("GEOID", "") not in scraped_index or scraped_index[j["GEOID"]]["is_stale"]
            ]
            logger.info(f"Incremental filter: {before} → {len(jurisdictions)} to process")
        return jurisdictions

    def _save_results(self, results: List[Dict[str, Any]], suffix: str = "") -> None:
        if not results:
            logger.warning("No discovery results to persist")
            return
        conn = self._conn()
        rows_by_table: Dict[str, List[tuple]] = {}
        for r in results:
            j = r.get("jurisdiction") or {}
            jtype = (j.get("type") or "city").lower()
            tbl = _scraped_table_for(jtype)
            row = _result_to_scraped_row(r)
            geoid, usps, _jt, hp, hpf, gsa, dsrc, status, score, payload = row
            if not geoid:
                continue
            rows_by_table.setdefault(tbl, []).append(
                (geoid, usps, hp, hpf, gsa, dsrc, status, score, Json(payload))
            )

        sql = """
            INSERT INTO {tbl} (
                geoid, usps, homepage_url, homepage_final_url, gsa_matched_domain,
                discovery_source, status, completeness_score, payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geoid) DO UPDATE SET
                usps = EXCLUDED.usps,
                discovered_at = NOW(),
                homepage_url = EXCLUDED.homepage_url,
                homepage_final_url = EXCLUDED.homepage_final_url,
                gsa_matched_domain = EXCLUDED.gsa_matched_domain,
                discovery_source = EXCLUDED.discovery_source,
                status = EXCLUDED.status,
                completeness_score = EXCLUDED.completeness_score,
                payload = EXCLUDED.payload
        """
        try:
            with conn.cursor() as cur:
                for tbl, rows in rows_by_table.items():
                    if not rows:
                        continue
                    execute_batch(cur, sql.format(tbl=tbl), rows, page_size=500)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.exception(
                "Postgres upsert into *_scraped failed (rolled back): {} — table sample: {}",
                exc,
                list(rows_by_table.keys())[:3],
            )
            raise
        inserted = sum(len(v) for v in rows_by_table.values())
        if inserted == 0:
            logger.warning(
                "No rows written to bronze *_scraped ({} discovery result(s) had no usable GEOID or empty jurisdiction). "
                "Check logs for 'No jurisdictions to process' or KeyError on jurisdiction rows.",
                len(results),
            )
        else:
            logger.success(
                "Upserted {:,} row(s) into bronze *_scraped across {} table(s) ({} discovery result(s))",
                inserted,
                len(rows_by_table),
                len(results),
            )

        if self.write_parquet_backup:
            super()._save_results(results, suffix)

    async def run_gsa_bulk_only(
        self,
        *,
        state_filter: Optional[str] = None,
        limit: Optional[int] = None,
        include_states: bool = False,
        include_municipalities: bool = True,
        include_counties: bool = True,
        include_schools: bool = False,
    ) -> Dict[str, int]:
        """
        Fast path: join bronze jurisdictions to ``intermediate.int_jurisdiction_websites`` by
        ``jurisdiction_id`` (no per-site HTTP discovery). Writes ``discovery_source='int_jurisdiction_websites_bulk'``.
        CLI flag ``--gsa-bulk-only`` is kept for backward compatibility.
        """
        conn = self._conn()
        self._ensure_int_jurisdiction_websites_cache()
        assert self._ijw_by_jurisdiction_id is not None
        ijw = self._ijw_by_jurisdiction_id
        jurisdictions = load_jurisdictions_from_postgres(
            conn,
            state_filter=state_filter,
            top_n=limit,
            include_states=include_states,
            include_municipalities=include_municipalities,
            include_counties=include_counties,
            include_schools=include_schools,
        )
        now = datetime.now(timezone.utc).isoformat()
        batch: Dict[str, List[tuple]] = {}
        matched = 0
        for j in jurisdictions:
            jt = j.get("type") or "city"
            geoid = j.get("GEOID") or ""
            st = j.get("state_code") or ""
            if not geoid:
                continue
            pk = jurisdiction_pk_from_geoid(str(geoid), str(jt))
            url = ijw.get(pk) if pk else None
            if not url:
                continue
            u = url.strip()
            if not u.lower().startswith(("http://", "https://")):
                u = f"https://{u.lstrip('/')}"
            dom = normalize_gov_host(u)
            matched += 1
            tbl = _scraped_table_for(jt)
            payload = {
                "websites": [
                    {
                        "url": u,
                        "final_url": u,
                        "status": "active",
                        "discovery_method": "int_jurisdiction_websites",
                    }
                ],
                "jurisdiction": j,
                "discovery_timestamp": now,
            }
            batch.setdefault(tbl, []).append(
                (
                    geoid,
                    st.upper(),
                    u,
                    u,
                    dom,
                    "int_jurisdiction_websites_bulk",
                    "success",
                    0.25,
                    Json(payload),
                )
            )

        sql = """
            INSERT INTO {tbl} (
                geoid, usps, homepage_url, homepage_final_url, gsa_matched_domain,
                discovery_source, status, completeness_score, payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geoid) DO UPDATE SET
                usps = EXCLUDED.usps,
                discovered_at = NOW(),
                homepage_url = EXCLUDED.homepage_url,
                homepage_final_url = EXCLUDED.homepage_final_url,
                gsa_matched_domain = EXCLUDED.gsa_matched_domain,
                discovery_source = EXCLUDED.discovery_source,
                status = EXCLUDED.status,
                completeness_score = EXCLUDED.completeness_score,
                payload = EXCLUDED.payload
        """
        with conn.cursor() as cur:
            for tbl, rows in batch.items():
                execute_batch(cur, sql.format(tbl=tbl), rows, page_size=500)
        conn.commit()
        logger.success(
            "int_jurisdiction_websites bulk: matched {:,} jurisdiction(s) across {:,} candidates",
            matched,
            len(jurisdictions),
        )
        return {
            "candidates": len(jurisdictions),
            "gsa_matched": matched,
            "tables": len(batch),
        }

    async def run_full_pipeline(
        self,
        discovery_limit: Optional[int] = None,
        state_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Legacy hook for ``main.py discover-jurisdictions``: ensure DDL, load bronze, deep discover.

        Does **not** re-ingest Census into bronze (no Spark). Writes to ``*_scraped`` only.
        """
        t0 = datetime.now()
        ensure_scraped_tables(self._conn())
        tf = (type_filter or "").strip().lower() or None
        if tf is None:
            inc_m, inc_c, inc_s, inc_states = True, True, False, False
        elif tf == "county":
            inc_m, inc_c, inc_s, inc_states = False, True, False, False
        elif tf in ("municipality", "city", "place"):
            inc_m, inc_c, inc_s, inc_states = True, False, False, False
        elif tf in ("school_district", "school"):
            inc_m, inc_c, inc_s, inc_states = False, False, True, False
        elif tf in ("state", "states"):
            inc_m, inc_c, inc_s, inc_states = False, False, False, True
        else:
            inc_m, inc_c, inc_s, inc_states = True, True, False, False

        jurisdictions = self.load_jurisdictions(
            state_filter=state_filter,
            top_n=discovery_limit,
            include_states=inc_states,
            include_municipalities=inc_m,
            include_counties=inc_c,
            include_schools=inc_s,
        )
        if not jurisdictions:
            return {
                "status": "complete",
                "bronze_records": 0,
                "urls_discovered": 0,
                "scraping_targets": 0,
                "elapsed_seconds": (datetime.now() - t0).total_seconds(),
                "silver_status": "skipped",
                "gold_status": "skipped",
            }
        await self.discover_batch(
            jurisdictions,
            save_interval=max(25, min(100, len(jurisdictions))),
        )
        elapsed = (datetime.now() - t0).total_seconds()
        n = len(jurisdictions)
        return {
            "status": "complete",
            "bronze_records": n,
            "urls_discovered": n,
            "scraping_targets": n,
            "elapsed_seconds": elapsed,
            "silver_status": "complete",
            "gold_status": "complete",
        }


# Backwards-compatible name for older imports
DiscoveryPipeline = JurisdictionDiscoveryPipeline


async def _async_main() -> None:
    parser = argparse.ArgumentParser(description="Postgres jurisdiction discovery → bronze *_scraped")
    parser.add_argument("--state", type=str, help="USPS filter, e.g. AL (omit with --all-states for every state)")
    parser.add_argument(
        "--all-states",
        action="store_true",
        help="Process municipalities + counties (+ schools if --all-types) for all states (no USPS filter). "
        "Large and slow — use --limit during tests.",
    )
    parser.add_argument("--limit", type=int, help="Max rows per jurisdiction class from bronze")
    # School districts are included by default (seeded from intermediate.int_jurisdiction_websites).
    # Opt-out exists because school runs are large.
    parser.add_argument(
        "--no-schools",
        action="store_true",
        help="Do NOT process school districts (default is to include them).",
    )
    parser.add_argument(
        "--include-states",
        action="store_true",
        help="Include rows from bronze.bronze_jurisdictions_states (state portal discovery)",
    )
    parser.add_argument("--gsa-bulk-only", action="store_true", help="Only GSA domain matching (no deep HTTP crawl)")
    parser.add_argument(
        "--wikidata",
        action="store_true",
        help="Enable Wikidata enrichment (default OFF; can be slow / rate-limited).",
    )
    parser.add_argument(
        "--truncate-scraped",
        action="store_true",
        help="Before run: DELETE *_scraped rows for --state USPS, or TRUNCATE every *_scraped table if --all-states or no state.",
    )
    parser.add_argument("--no-incremental", action="store_true")
    parser.add_argument("--max-concurrent", type=int, default=8)
    parser.add_argument("--youtube-api-key", type=str, default=os.getenv("YOUTUBE_DATA_API_KEY"))
    parser.add_argument("--parquet-backup", action="store_true", help="Also write legacy gold parquet summary")
    parser.add_argument(
        "--skip-ddl",
        action="store_true",
        help="Do not run CREATE TABLE (tables must already exist)",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Postgres URL (default: env after loading .env, then local docker per target_database_url)",
    )
    args = parser.parse_args()

    pipeline = JurisdictionDiscoveryPipeline(
        database_url=args.database_url,
        youtube_api_key=args.youtube_api_key,
        max_concurrent=args.max_concurrent,
        incremental=not args.no_incremental,
        write_parquet_backup=args.parquet_backup,
        wikidata_enabled=args.wikidata,
    )
    try:
        if not args.skip_ddl:
            ensure_scraped_tables(pipeline._conn())
        state_filter = None if args.all_states else args.state
        if args.all_states and args.state:
            logger.error("Use either --all-states or --state XX, not both.")
            return

        if args.truncate_scraped:
            # With --state AL: remove only AL rows. With --all-states or no state: empty all scraped tables.
            clean_scraped_tables(
                pipeline._conn(),
                state_filter=state_filter,
            )

        if args.gsa_bulk_only:
            await pipeline.run_gsa_bulk_only(
                state_filter=state_filter,
                limit=args.limit,
                include_states=args.include_states,
                include_municipalities=True,
                include_counties=True,
                include_schools=not args.no_schools,
            )
            return

        jurisdictions = pipeline.load_jurisdictions(
            state_filter=state_filter,
            top_n=args.limit,
            include_states=args.include_states,
            include_municipalities=True,
            include_counties=True,
            include_schools=not args.no_schools,
        )
        if not jurisdictions:
            logger.warning("No jurisdictions to process")
            return
        if len(jurisdictions) > 200 and not state_filter and not args.all_states:
            logger.error(
                "Refusing unbounded national run without --state (safety). "
                "Pass --state XX, or --all-states to process every state, or use --limit."
            )
            return
        await pipeline.discover_batch(jurisdictions, save_interval=max(25, min(100, len(jurisdictions))))
    finally:
        pipeline.close()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
