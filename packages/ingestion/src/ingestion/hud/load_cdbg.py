"""Load HUD CDBG activity-level spending into bronze.

    python -m ingestion.hud.load_cdbg
    python -m ingestion.hud.load_cdbg --limit 5000 --dry-run

Source: HUD Open Data (eGIS) "Community Development Block Grant Activity" feature service
(public data, HUD-published, https://hudgis-hud.opendata.arcgis.com/). One row per IDIS
activity: grantee, HUD activity group, matrix-code activity name, funding amount and
completion date. About 400,000 activities since 1996.

Privacy: the service also carries each activity's street address, ZIP and point
location. Activities such as housing rehabilitation can sit at a private resident's home,
so those columns are NOT loaded. Only grantee-level fields are kept.

Formula allocations are not loaded here: HUD Exchange publishes them only on pages that
return 404 to automated clients; the allocation mart is derived from USAspending
CDBG awards (assistance listings 14.218 and 14.228) already in the warehouse.
"""

from __future__ import annotations

import argparse
import time
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import text

from ..pgutil import get_engine

SERVICE = "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/CDBG_PROGRAM_ACTIVITY/FeatureServer/0"
USER_AGENT = "open-navigator (civic data research; https://github.com/getcommunityone/open-navigator)"
PAGE = 2000
DELAY_S = 0.5
TABLE = "bronze.bronze_hud_cdbg_activity"
DATA_SOURCE = "HUD Open Data: Community Development Block Grant Activity"

_FIELDS = "OBJECTID,GRANTEE,GRANTEE_TYPE,GRANTEE_ID,IDIS_ACTV_ID,STATE,GROUPING,NAME,ALIAS,ACTV_FUNDING_AMT,COMPLETED_DT"

_DDL = [
    "CREATE SCHEMA IF NOT EXISTS bronze",
    f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        objectid BIGINT PRIMARY KEY,
        grantee TEXT,
        grantee_type TEXT,
        grantee_id TEXT,
        idis_activity_id TEXT,
        state_code TEXT,
        activity_group TEXT,
        activity_name TEXT,
        activity_alias TEXT,
        funding_amount NUMERIC(16,2),
        completed_date TEXT,
        data_source TEXT,
        ingestion_date TIMESTAMP DEFAULT NOW()
    )""",
    f"CREATE INDEX IF NOT EXISTS idx_hud_cdbg_grantee ON {TABLE}(grantee_id)",
]
_COLS = [
    "objectid", "grantee", "grantee_type", "grantee_id", "idis_activity_id", "state_code",
    "activity_group", "activity_name", "activity_alias", "funding_amount", "completed_date", "data_source",
]
_UPSERT = text(
    f"INSERT INTO {TABLE} ({', '.join(_COLS)}) VALUES ({', '.join(':' + c for c in _COLS)}) "
    f"ON CONFLICT (objectid) DO UPDATE SET "
    + ", ".join(f"{c}=EXCLUDED.{c}" for c in _COLS[1:])
    + ", ingestion_date = NOW()"
)


def _id(v: Any) -> str | None:
    return None if v is None else str(int(v))


def to_record(attrs: dict[str, Any]) -> dict[str, Any]:
    return {
        "objectid": attrs["OBJECTID"],
        "grantee": (attrs.get("GRANTEE") or "").strip() or None,
        "grantee_type": _id(attrs.get("GRANTEE_TYPE")),
        "grantee_id": _id(attrs.get("GRANTEE_ID")),
        "idis_activity_id": _id(attrs.get("IDIS_ACTV_ID")),
        "state_code": (attrs.get("STATE") or "").strip() or None,
        "activity_group": (attrs.get("GROUPING") or "").strip() or None,
        "activity_name": (attrs.get("NAME") or "").strip() or None,
        "activity_alias": (attrs.get("ALIAS") or "").strip() or None,
        "funding_amount": attrs.get("ACTV_FUNDING_AMT"),
        "completed_date": (attrs.get("COMPLETED_DT") or "").strip() or None,
        "data_source": DATA_SOURCE,
    }


def iter_pages(client: httpx.Client, limit: int | None):
    last_id = 0  # keyset paging on OBJECTID: much faster on the service than resultOffset
    fetched = 0
    while True:
        for attempt in range(6):
            try:
                resp = client.get(
                    f"{SERVICE}/query",
                    params={
                        "where": f"OBJECTID > {last_id}", "outFields": _FIELDS, "returnGeometry": "false",
                        "orderByFields": "OBJECTID",
                        "resultRecordCount": PAGE, "f": "json",
                    },
                )
                resp.raise_for_status()
                body = resp.json()
                if "error" in body:
                    raise RuntimeError(body["error"])
                break
            except (httpx.HTTPError, RuntimeError) as exc:
                logger.warning("page after OBJECTID {} failed ({}); attempt {}", last_id, exc, attempt + 1)
                time.sleep(min(3 * 2**attempt, 60))
        else:
            raise RuntimeError(f"HUD CDBG service failed after OBJECTID {last_id}")
        feats = body.get("features", [])
        if not feats:
            return
        rows = [to_record(f["attributes"]) for f in feats]
        yield rows
        last_id = max(r["objectid"] for r in rows)
        fetched += len(rows)
        if limit and fetched >= limit:
            return
        time.sleep(DELAY_S)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load HUD CDBG activities into bronze")
    p.add_argument("--limit", type=int)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)

    engine = None if a.dry_run else get_engine()
    if engine is not None:
        with engine.begin() as cx:
            for stmt in _DDL:
                cx.execute(text(stmt))
    total = 0
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=90) as client:
        for batch in iter_pages(client, a.limit):
            total += len(batch)
            if engine is not None:
                with engine.begin() as cx:
                    cx.execute(_UPSERT, batch)
            if total % 40000 < PAGE:
                logger.info("{:,} activities", total)
    if engine is not None:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as cx:
            cx.execute(text(f"ANALYZE {TABLE}"))
    logger.success("Loaded {:,} CDBG activities into {}", total, TABLE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
