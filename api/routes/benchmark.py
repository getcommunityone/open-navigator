"""Peer benchmarking — GET /api/benchmark/{metric} (#1392, #1393).

Compares one jurisdiction with peers on a metric built from real warehouse data.
Peers are either explicit (``peers=id1,id2``) or automatic (``peers=auto``):
same jurisdiction type, Census population within 0.5x-2x, the same state first and
the rest of the same Census region second, closest population first. For auto peers,
candidates that HAVE data for the metric are preferred, and the response says so.

No fabricated numbers: a jurisdiction with no matched rows has ``value: null`` (not 0)
and is left out of the rank. Fiscal years are strings on the wire.

Metrics live in ``METRICS``; later sources (CDBG, payroll, opioid settlements) add an
entry each. Tables are resolved unqualified through the connection search_path.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])

DEFAULT_PEERS = 5
MAX_PEERS = 15
CANDIDATE_POOL = 200

# U.S. Census Bureau regions (reference constant).
CENSUS_REGIONS: dict[str, tuple[str, ...]] = {
    "Northeast": ("CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"),
    "Midwest": ("IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"),
    "South": ("DE", "DC", "FL", "GA", "MD", "NC", "SC", "VA", "WV", "AL", "KY", "MS", "TN",
              "AR", "LA", "OK", "TX"),
    "West": ("AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"),
}


def region_of(state_code: str | None) -> str | None:
    for name, states in CENSUS_REGIONS.items():
        if state_code in states:
            return name
    return None


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: str  # "dollars"
    source: str
    # SQL returning (jurisdiction_id, value, as_of) for $1 = text[] ids, $2 = int fiscal year or NULL.
    values_sql: str
    note: str = ""


_USASPENDING = "USAspending.gov (U.S. Treasury), assistance awards to local governments, public domain"

_FUNDING_BY_ALN = """
    SELECT jurisdiction_id, sum(total_obligation) AS value, max(source_updated_at) AS as_of
    FROM jurisdiction_federal_funding
    WHERE jurisdiction_id = ANY($1::text[])
      AND ($2::int IS NULL OR fiscal_year = $2::int)
      {extra}
    GROUP BY jurisdiction_id
"""

METRICS: dict[str, Metric] = {
    "federal_total": Metric(
        "federal_total", "Federal assistance awards (all programs)", "dollars", _USASPENDING,
        _FUNDING_BY_ALN.format(extra=""),
        "Sum of total obligations of grants and cooperative agreements matched to the jurisdiction, FY2019 onward.",
    ),
    "federal_cdbg": Metric(
        "federal_cdbg", "Federal CDBG awards", "dollars", _USASPENDING,
        _FUNDING_BY_ALN.format(extra="AND assistance_listing_number IN ('14.218', '14.228')"),
        "Community Development Block Grants: Entitlement (14.218) and State / Non-entitlement (14.228).",
    ),
    "federal_opioid": Metric(
        "federal_opioid", "Federal opioid-related awards", "dollars", _USASPENDING + "; award text",
        """
        SELECT jurisdiction_id, sum(total_obligation) AS value, max(source_updated_at) AS as_of
        FROM federal_award
        WHERE jurisdiction_id = ANY($1::text[])
          AND ($2::int IS NULL OR fiscal_year = $2::int)
          AND (assistance_listing_number IN ('93.788', '16.838')
               OR description ~* 'opioid')
        GROUP BY jurisdiction_id
        """,
        "Awards under SAMHSA Opioid STR (93.788) and DOJ COSSUP (16.838), plus any award whose description mentions opioids.",
    ),
}


def select_peers(
    candidates: list[dict[str, Any]], target_state: str | None, n: int
) -> list[dict[str, Any]]:
    """Pick ``n`` peers: same state first, then has-data, then closest population.

    ``candidates`` are dicts with ``state_code``, ``has_data`` and ``pop_distance``.
    """
    ranked = sorted(
        candidates,
        key=lambda c: (
            c["state_code"] != target_state,
            not c["has_data"],
            c["pop_distance"],
            c["jurisdiction_id"],
        ),
    )
    return ranked[:n]


def rank_among(values: dict[str, float | None], target_id: str) -> dict[str, Any] | None:
    """Rank the target among ids with a non-null value (1 = highest)."""
    have = {k: v for k, v in values.items() if v is not None}
    if target_id not in have:
        return None
    order = sorted(have.values(), reverse=True)
    rank = order.index(have[target_id]) + 1
    return {"rank": rank, "of": len(order)}


class BenchmarkEntity(BaseModel):
    jurisdiction_id: str
    name: str
    jurisdiction_type: str
    state_code: str | None = None
    state: str | None = None
    population: int | None = None
    value: float | None = None  # total dollars; null = no matched data
    per_capita: float | None = None


class BenchmarkResponse(BaseModel):
    metric: str
    label: str
    unit: str
    fiscal_year: str | None = None  # string on the wire; null = all years loaded
    jurisdiction: BenchmarkEntity
    peers: list[BenchmarkEntity]
    peer_selection: str
    peer_median_per_capita: float | None = None
    rank_per_capita: dict[str, int] | None = None
    data_as_of: str | None = None
    source: str
    note: str = ""


_JUR_COLS = "jurisdiction_id, name, jurisdiction_type, state_code, state_name, population"


def _entity(row: Any, value: float | None) -> BenchmarkEntity:
    pop = row["population"]
    val = float(value) if value is not None else None
    return BenchmarkEntity(
        jurisdiction_id=row["jurisdiction_id"], name=row["name"],
        jurisdiction_type=row["jurisdiction_type"], state_code=row["state_code"],
        state=row["state_name"], population=int(pop) if pop else None, value=val,
        per_capita=round(val / pop, 2) if (val is not None and pop) else None,
    )


@router.get("/{metric}", response_model=BenchmarkResponse)
async def benchmark(
    metric: str,
    jurisdiction_id: str = Query(..., min_length=1, max_length=200),
    peers: str = Query("auto", description="'auto' or comma-separated jurisdiction_ids"),
    n: int = Query(DEFAULT_PEERS, ge=1, le=MAX_PEERS, description="Auto-peer count"),
    fiscal_year: int | None = Query(None, ge=2000, le=2100),
) -> BenchmarkResponse:
    spec = METRICS.get(metric)
    if spec is None:
        raise HTTPException(404, detail=f"Unknown metric. Available: {', '.join(sorted(METRICS))}")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET statement_timeout = '15s'")
        target = await conn.fetchrow(
            f"SELECT {_JUR_COLS} FROM jurisdictions WHERE jurisdiction_id = $1", jurisdiction_id
        )
        if target is None:
            raise HTTPException(404, detail="Unknown jurisdiction_id")

        explicit = [p.strip() for p in peers.split(",") if p.strip()] if peers != "auto" else None
        if explicit is not None:
            if len(explicit) > MAX_PEERS:
                raise HTTPException(400, detail=f"At most {MAX_PEERS} peers")
            peer_rows = await conn.fetch(
                f"SELECT {_JUR_COLS} FROM jurisdictions WHERE jurisdiction_id = ANY($1::text[])", explicit
            )
            if len(peer_rows) != len(set(explicit)):
                raise HTTPException(404, detail="One or more peer ids are unknown")
            selection = "explicit: peers chosen by the caller"
            values = await _values(conn, spec, [target["jurisdiction_id"], *[r["jurisdiction_id"] for r in peer_rows]], fiscal_year)
        else:
            pop = target["population"]
            if not pop:
                raise HTTPException(422, detail="Jurisdiction has no Census population; pass explicit peers")
            region_states = list(CENSUS_REGIONS.get(region_of(target["state_code"]) or "", ()) or [target["state_code"]])
            cand_rows = await conn.fetch(
                f"""
                SELECT {_JUR_COLS}
                FROM jurisdictions
                WHERE jurisdiction_type = $1 AND state_code = ANY($2::text[])
                  AND population BETWEEN $3 AND $4 AND jurisdiction_id <> $5
                ORDER BY abs(ln(population::float8 / $6::float8)) LIMIT {CANDIDATE_POOL}
                """,
                target["jurisdiction_type"], region_states, int(pop * 0.5), int(pop * 2),
                jurisdiction_id, float(pop),
            )
            values = await _values(
                conn, spec, [jurisdiction_id, *[r["jurisdiction_id"] for r in cand_rows]], fiscal_year
            )
            cands = [
                {
                    "jurisdiction_id": r["jurisdiction_id"], "state_code": r["state_code"],
                    "has_data": values.get(r["jurisdiction_id"], (None, None))[0] is not None,
                    "pop_distance": abs(math.log(r["population"] / pop)), "row": r,
                }
                for r in cand_rows
            ]
            chosen = select_peers(cands, target["state_code"], n)
            peer_rows = [c["row"] for c in chosen]
            with_data = sum(1 for c in chosen if c["has_data"])
            selection = (
                f"auto: {len(peer_rows)} {target['jurisdiction_type']} peers with population within 0.5x-2x "
                f"of {pop:,}, same state first then the {region_of(target['state_code'])} Census region, "
                f"preferring peers with matched data ({with_data} of {len(peer_rows)} have it)"
            )

    t_entity = _entity(target, values.get(target["jurisdiction_id"], (None, None))[0])
    p_entities = [_entity(r, values.get(r["jurisdiction_id"], (None, None))[0]) for r in peer_rows]
    pcs = {e.jurisdiction_id: e.per_capita for e in [t_entity, *p_entities]}
    peer_pc = sorted(e.per_capita for e in p_entities if e.per_capita is not None)
    median = None
    if peer_pc:
        mid = len(peer_pc) // 2
        median = peer_pc[mid] if len(peer_pc) % 2 else round((peer_pc[mid - 1] + peer_pc[mid]) / 2, 2)
    as_ofs = [v[1] for v in values.values() if v[1] is not None]
    return BenchmarkResponse(
        metric=spec.key, label=spec.label, unit=spec.unit,
        fiscal_year=str(fiscal_year) if fiscal_year else None,
        jurisdiction=t_entity, peers=p_entities, peer_selection=selection,
        peer_median_per_capita=median, rank_per_capita=rank_among(pcs, jurisdiction_id),
        data_as_of=max(as_ofs).isoformat() if as_ofs else None,
        source=spec.source, note=spec.note,
    )


async def _values(conn: Any, spec: Metric, ids: list[str], fiscal_year: int | None) -> dict[str, tuple]:
    try:
        rows = await conn.fetch(spec.values_sql, ids, fiscal_year)
    except Exception as exc:  # table not built in this environment
        logger.warning("benchmark {} unavailable: {}", spec.key, exc)
        raise HTTPException(503, detail="Benchmark data is not available in this environment") from exc
    return {r["jurisdiction_id"]: (r["value"], r["as_of"]) for r in rows}
