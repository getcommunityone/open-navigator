"""
Use ``fips_gnis_map.parquet`` (dump extract) for Census identifier → Wikidata Q-id.

Parquet rows have ``qid``, ``fips``, ``gnis`` — not official websites. Websites come from
``wbgetentities`` in :mod:`load_jurisdictions_wikidata` after Q-ids are known.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterator, Optional, Set, Tuple

from loguru import logger

from scripts.datasources.wikidata.geography_qid_cache import GeographyQidCache, norm_lit


def resolve_fips_gnis_parquet_path(explicit: Path | str | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    raw = (os.getenv("WIKIDATA_FIPS_GNIS_PARQUET") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(os.getenv("WIKIDATA_CACHE_DIR", "data/cache/wikidata")).resolve() / "fips_gnis_map.parquet"


def iter_parquet_rows(parquet_path: Path, batch_size: int = 100_000) -> Iterator[Tuple[str, Optional[str], Optional[str]]]:
    """Stream parquet rows without loading the full file (PyArrow ``iter_batches``)."""
    import pyarrow.parquet as pq

    want = ("qid", "fips", "gnis")
    schema_names = pq.read_schema(parquet_path).names
    columns = [c for c in want if c in schema_names]
    if "qid" not in columns:
        raise ValueError(f"Parquet missing 'qid' column; found columns: {schema_names}")

    pf = pq.ParquetFile(parquet_path)
    for batch in pf.iter_batches(batch_size=batch_size, columns=columns):
        for row in batch.to_pandas().itertuples(index=False):
            qid = str(getattr(row, "qid", "") or "").strip()
            if not qid.startswith("Q"):
                continue
            fips = getattr(row, "fips", None)
            gnis = getattr(row, "gnis", None)
            fips_s = str(fips).strip() if fips is not None and str(fips).strip() else None
            gnis_s = str(gnis).strip() if gnis is not None and str(gnis).strip() else None
            yield qid, fips_s, gnis_s


def warm_geography_qid_cache_from_parquet(
    qcache: GeographyQidCache,
    parquet_path: Path,
    *,
    batch_size: int = 100_000,
) -> Dict[str, int]:
    """Load every parquet row into ``geography_qid_mapping_v1.json`` via :class:`GeographyQidCache`."""
    if not parquet_path.is_file():
        raise FileNotFoundError(f"Parquet not found: {parquet_path}")

    n_rows = 0
    n_keys = 0
    before = len(qcache._entries)

    for qid, fips, gnis in iter_parquet_rows(parquet_path, batch_size=batch_size):
        n_rows += 1
        if fips:
            qcache.remember_muni(qid, fips, None)
            qcache.remember_county(qid, fips, None, None)
            qcache.remember_school(qid, fips, None, None)
            n_keys += 1
        if gnis:
            qcache.remember_muni(qid, None, gnis)
            qcache.remember_county(qid, None, None, gnis)
            qcache.remember_school(qid, None, gnis, None)
            n_keys += 1
        if n_rows % 500_000 == 0:
            logger.info(f"  parquet warm: {n_rows:,} rows scanned…")

    qcache.save()
    added = len(qcache._entries) - before
    return {"parquet_rows": n_rows, "cache_keys_added": max(0, added)}


def load_parquet_to_postgres(parquet_path: Path, database_url: str) -> int:
    """Create/replace ``jurisdiction_wikidata_fips_gnis_map`` from parquet (fast SQL joins)."""
    import pandas as pd
    import psycopg2
    from psycopg2.extras import execute_values

    if not parquet_path.is_file():
        raise FileNotFoundError(parquet_path)

    logger.info(f"Reading {parquet_path}…")
    df = pd.read_parquet(parquet_path, columns=["qid", "label", "fips", "gnis", "modified", "source"])
    records = []
    for row in df.itertuples(index=False):
        qid = str(getattr(row, "qid", "") or "").strip()
        if not qid.startswith("Q"):
            continue
        records.append(
            (
                qid,
                str(getattr(row, "label", "") or "") or None,
                str(getattr(row, "fips", "") or "").strip() or None,
                str(getattr(row, "gnis", "") or "").strip() or None,
                int(getattr(row, "modified", 0) or 0) or None,
                str(getattr(row, "source", "") or "") or None,
            )
        )

    logger.info(f"Writing {len(records):,} rows to jurisdiction_wikidata_fips_gnis_map…")
    conn = psycopg2.connect(database_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS jurisdiction_wikidata_fips_gnis_map")
                cur.execute(
                    """
                    CREATE TABLE jurisdiction_wikidata_fips_gnis_map (
                        qid      TEXT NOT NULL,
                        label    TEXT,
                        fips     TEXT,
                        gnis     TEXT,
                        modified BIGINT,
                        source   TEXT
                    )
                    """
                )
                cur.execute(
                    "CREATE INDEX idx_jurisdiction_wikidata_fips_gnis_fips ON jurisdiction_wikidata_fips_gnis_map (fips) WHERE fips IS NOT NULL"
                )
                cur.execute(
                    "CREATE INDEX idx_jurisdiction_wikidata_fips_gnis_gnis ON jurisdiction_wikidata_fips_gnis_map (gnis) WHERE gnis IS NOT NULL"
                )
                execute_values(
                    cur,
                    """
                    INSERT INTO jurisdiction_wikidata_fips_gnis_map (qid, label, fips, gnis, modified, source)
                    VALUES %s
                    """,
                    records,
                    page_size=5000,
                )
    finally:
        conn.close()
    return len(records)


def lookup_qid_from_literals(
    fips_literals: Set[str],
    gnis_literals: Set[str],
    fips_index: Dict[str, str],
    gnis_index: Dict[str, str],
) -> Optional[str]:
    for lit in fips_literals:
        q = fips_index.get(norm_lit(lit))
        if q:
            return q
    for lit in gnis_literals:
        q = gnis_index.get(norm_lit(lit))
        if q:
            return q
    return None


def build_parquet_indexes(parquet_path: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    """In-memory fips/gnis → qid maps (use for moderate parquet sizes or one state)."""
    fips_index: Dict[str, str] = {}
    gnis_index: Dict[str, str] = {}
    for qid, fips, gnis in iter_parquet_rows(parquet_path):
        if fips:
            fips_index[norm_lit(fips)] = qid
        if gnis:
            gnis_index[norm_lit(gnis)] = qid
    return fips_index, gnis_index


def _postgres_lookup_table_ready(conn) -> bool:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'jurisdiction_wikidata_fips_gnis_map'
            """
        )
        return cur.fetchone() is not None
    finally:
        cur.close()


def apply_parquet_qids_to_bronze_municipalities(conn, state_code: str, parquet_path: Path) -> int:
    us = state_code.upper()
    if _postgres_lookup_table_ready(conn):
        cur = conn.cursor()
        n = 0
        try:
            cur.execute(
                """
                UPDATE bronze.bronze_jurisdictions_municipalities_wikidata w
                SET wikidata_id = p.qid
                FROM bronze.bronze_jurisdictions_municipalities m
                JOIN jurisdiction_wikidata_fips_gnis_map p
                  ON REPLACE(m.geoid::text, '-', '') = REPLACE(BTRIM(p.fips), '-', '')
                WHERE m.usps = %s AND w.usps = m.usps AND w.geoid::text = m.geoid::text
                  AND p.fips IS NOT NULL AND BTRIM(p.fips) <> ''
                  AND (w.wikidata_id IS NULL OR BTRIM(wikidata_id::text) = '')
                """,
                (us,),
            )
            n += cur.rowcount
            cur.execute(
                """
                UPDATE bronze.bronze_jurisdictions_municipalities_wikidata w
                SET wikidata_id = p.qid
                FROM bronze.bronze_jurisdictions_municipalities m
                JOIN jurisdiction_wikidata_fips_gnis_map p
                  ON REPLACE(BTRIM(m.ansicode::text), '-', '') = REPLACE(BTRIM(p.gnis), '-', '')
                WHERE m.usps = %s AND w.usps = m.usps AND w.geoid::text = m.geoid::text
                  AND m.ansicode IS NOT NULL AND BTRIM(m.ansicode::text) <> ''
                  AND p.gnis IS NOT NULL AND BTRIM(p.gnis) <> ''
                  AND (w.wikidata_id IS NULL OR BTRIM(wikidata_id::text) = '')
                """,
                (us,),
            )
            n += cur.rowcount
            conn.commit()
        finally:
            cur.close()
        return n

    from scripts.datasources.wikidata.load_jurisdictions_wikidata import _municipality_wd_literal_sets

    fips_index, gnis_index = build_parquet_indexes(parquet_path)
    cur = conn.cursor()
    updated = 0
    try:
        cur.execute(
            """
            SELECT geoid::text, ansicode::text
            FROM bronze.bronze_jurisdictions_municipalities
            WHERE usps = %s
            """,
            (us,),
        )
        for geoid, ansicode in cur.fetchall():
            ff, gg = _municipality_wd_literal_sets(geoid, ansicode)
            qid = lookup_qid_from_literals(ff, gg, fips_index, gnis_index)
            if not qid:
                continue
            cur.execute(
                """
                UPDATE bronze.bronze_jurisdictions_municipalities_wikidata
                SET wikidata_id = %s
                WHERE usps = %s AND geoid::text = %s
                  AND (wikidata_id IS NULL OR BTRIM(wikidata_id::text) = '')
                """,
                (qid, us, str(geoid).strip()),
            )
            updated += cur.rowcount
        conn.commit()
    finally:
        cur.close()
    return updated


def apply_parquet_qids_to_bronze_counties(conn, state_code: str, parquet_path: Path) -> int:
    us = state_code.upper()
    if _postgres_lookup_table_ready(conn):
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE bronze.bronze_jurisdictions_counties_wikidata w
                SET wikidata_id = p.qid
                FROM bronze.bronze_jurisdictions_counties m
                JOIN jurisdiction_wikidata_fips_gnis_map p
                  ON REPLACE(m.geoid::text, '-', '') = REPLACE(BTRIM(p.fips), '-', '')
                WHERE m.usps = %s AND w.usps = m.usps AND w.geoid::text = m.geoid::text
                  AND p.fips IS NOT NULL AND BTRIM(p.fips) <> ''
                  AND (w.wikidata_id IS NULL OR BTRIM(wikidata_id::text) = '')
                """,
                (us,),
            )
            n = cur.rowcount
            conn.commit()
        finally:
            cur.close()
        return n

    from scripts.datasources.wikidata.load_jurisdictions_wikidata import (
        STATE_MAP,
        _county_fips_literal_alternatives,
    )

    fips_index, gnis_index = build_parquet_indexes(parquet_path)
    sf = STATE_MAP.get(us, {}).get("fips")
    cur = conn.cursor()
    updated = 0
    try:
        cur.execute(
            """
            SELECT geoid::text
            FROM bronze.bronze_jurisdictions_counties
            WHERE usps = %s
            """,
            (us,),
        )
        for (geoid,) in cur.fetchall():
            lits = _county_fips_literal_alternatives(geoid, sf)
            qid = lookup_qid_from_literals(lits, lits, fips_index, gnis_index)
            if not qid:
                continue
            cur.execute(
                """
                UPDATE bronze.bronze_jurisdictions_counties_wikidata
                SET wikidata_id = %s
                WHERE usps = %s AND geoid::text = %s
                  AND (wikidata_id IS NULL OR BTRIM(wikidata_id::text) = '')
                """,
                (qid, us, str(geoid).strip()),
            )
            updated += cur.rowcount
        conn.commit()
    finally:
        cur.close()
    return updated
