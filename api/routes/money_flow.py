"""
"Follow the money" flow endpoint — GET /api/money-flow.

Returns Sankey-flow data for three lenses, ALL traced to the warehouse (no
fabricated numbers, per CLAUDE.md):
  - spending : real money-flagged decisions (public.item_interestingness,
               net_dollar_impact), jurisdiction -> decision.
  - grants   : real 990 Schedule I grant flows (public.grant), grantor -> grantee.
  - economy  : a real decomposition of nonprofit sector revenue into its 990
               components (contributions / program-service / other) — an honest
               breakdown of one real total, NOT invented funder->grantee edges.

WIRE-FORMAT: every displayed number is a STRING (head_amount / value_label). The
link `value` stays NUMERIC because the Sankey layout needs it to size links — it
is a chart magnitude, not a bare number rendered to the user.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool, normalize_state_input

router = APIRouter(prefix="/api/money-flow", tags=["money-flow"])
tracer = trace.get_tracer(__name__)

_ACCENT = {"spending": "#ea580c", "grants": "#0d9488", "economy": "#7c3aed"}


def money_fmt(value: Any) -> str:
    """Compact dollar string: $3.5B / $1.2M / $4.5K / $850. Plain string (wire rule)."""
    if value is None:
        return "$0"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "$0"
    sign = "-" if amount < 0 else ""
    mag = abs(amount)
    if mag >= 1_000_000_000_000:
        return f"{sign}${mag / 1_000_000_000_000:.1f}T"
    if mag >= 1_000_000_000:
        return f"{sign}${mag / 1_000_000_000:.1f}B"
    if mag >= 1_000_000:
        return f"{sign}${mag / 1_000_000:.1f}M"
    if mag >= 1_000:
        return f"{sign}${mag / 1_000:.1f}K"
    return f"{sign}${mag:.0f}"


def _trunc(text: str, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class FlowMeta(BaseModel):
    title: str
    subtitle: Optional[str] = None
    url: Optional[str] = None
    source_label: Optional[str] = None


class FlowNode(BaseModel):
    name: str


class FlowLink(BaseModel):
    source: int
    target: int
    value: float  # numeric magnitude for the Sankey layout (not a user-facing bare number)
    value_label: str
    meta: FlowMeta


class FlowLens(BaseModel):
    accent: str
    head_amount: str = "—"
    head_label: str = ""
    count_label: str = ""
    nodes: List[FlowNode] = []
    links: List[FlowLink] = []
    placeholder: bool = True


class MoneyFlowResponse(BaseModel):
    location_label: str
    lenses: Dict[str, FlowLens]


# ---------------------------------------------------------------------------
# Per-lens builders (each defensive: failure -> placeholder, never a 500)
# ---------------------------------------------------------------------------
_SPENDING_SQL = """
    SELECT event_decision_id, title, net_dollar_impact, outcome, occurred_at,
           votes_yes, votes_no, total_votes
    FROM item_interestingness
    WHERE net_dollar_impact IS NOT NULL AND net_dollar_impact <> 0
      AND ($1::text IS NULL OR state_code = $1)
      AND ($2::text IS NULL OR jurisdiction_name ILIKE $2)
    ORDER BY abs(net_dollar_impact) DESC
    LIMIT 6
"""


async def _spending(conn, *, state_code: Optional[str], city: Optional[str], scope_label: str) -> FlowLens:
    lens = FlowLens(accent=_ACCENT["spending"])
    try:
        rows = await conn.fetch(_SPENDING_SQL, state_code, f"%{city}%" if city else None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("money-flow spending failed: {}", exc)
        return lens
    if not rows:
        return lens
    src = scope_label or "Local government"
    nodes = [FlowNode(name=_trunc(src, 24))]
    links: List[FlowLink] = []
    total = 0.0
    for r in rows:
        amt = abs(float(r["net_dollar_impact"]))
        total += amt
        nodes.append(FlowNode(name=_trunc(r["title"] or "Untitled decision", 40)))
        sub_parts = []
        if r["outcome"]:
            sub_parts.append(r["outcome"])
        if r["occurred_at"]:
            sub_parts.append(r["occurred_at"].isoformat())
        if (r["total_votes"] or 0) > 0:
            sub_parts.append(f"{r['votes_yes']}–{r['votes_no']}")
        links.append(FlowLink(
            source=0, target=len(nodes) - 1, value=amt, value_label=money_fmt(amt),
            meta=FlowMeta(
                title=r["title"] or "Untitled decision",
                subtitle=" · ".join(sub_parts) or None,
                url=f"/decisions/{r['event_decision_id']}",
                source_label="decision",
            ),
        ))
    lens.nodes, lens.links, lens.placeholder = nodes, links, False
    lens.head_amount = money_fmt(total)
    lens.head_label = "in tracked spending decisions"
    lens.count_label = f"{len(links)} decisions"
    return lens


_GRANTS_SQL = """
    SELECT grantor_name, grantee_name, amount, purpose, tax_year
    FROM "grant"
    WHERE amount IS NOT NULL AND amount > 0
      AND grantor_name IS NOT NULL AND grantee_name IS NOT NULL
      AND ($1::text IS NULL OR grantor_state_code = $1 OR grantee_state_code = $1)
    ORDER BY amount DESC
    LIMIT 6
"""


async def _grants(conn, *, state_code: Optional[str]) -> FlowLens:
    lens = FlowLens(accent=_ACCENT["grants"])
    try:
        rows = await conn.fetch(_GRANTS_SQL, state_code)
    except Exception as exc:  # noqa: BLE001
        logger.warning("money-flow grants failed: {}", exc)
        return lens
    if not rows:
        return lens
    idx: Dict[str, int] = {}
    nodes: List[FlowNode] = []

    def node_for(name: str) -> int:
        key = name.strip()
        if key not in idx:
            idx[key] = len(nodes)
            nodes.append(FlowNode(name=_trunc(key, 28)))
        return idx[key]

    links: List[FlowLink] = []
    total = 0.0
    for r in rows:
        s = node_for(r["grantor_name"])
        t = node_for(r["grantee_name"])
        amt = float(r["amount"])
        total += amt
        sub = " · ".join(
            p for p in [(r["purpose"] or "").strip(), f"FY{r['tax_year']}" if r["tax_year"] else ""] if p
        )
        links.append(FlowLink(
            source=s, target=t, value=amt, value_label=money_fmt(amt),
            meta=FlowMeta(title=r["grantee_name"], subtitle=sub or None,
                          url="/search?types=grants", source_label="990 Schedule I"),
        ))
    lens.nodes, lens.links, lens.placeholder = nodes, links, False
    lens.head_amount = money_fmt(total)
    lens.head_label = "in grant flows"
    lens.count_label = f"{len(links)} grants · 990 Schedule I"
    return lens


# Reads the one-row pre-aggregation mart (public.nonprofit_sector_revenue)
# instead of SUM-scanning the 3.6M-row mdm_organization_nonprofit satellite on
# every request (~590ms -> ~0.1ms). The figure is national (the satellite has no
# usable state column), so scope is always 'us'.
_ECONOMY_SQL = """
    SELECT contributions,
           program_service_revenue AS program,
           total_revenue           AS total,
           org_count               AS orgs
    FROM nonprofit_sector_revenue
    WHERE scope = 'us'
"""


async def _economy(conn) -> FlowLens:
    lens = FlowLens(accent=_ACCENT["economy"])
    try:
        row = await conn.fetchrow(_ECONOMY_SQL)
    except Exception as exc:  # noqa: BLE001
        logger.warning("money-flow economy failed: {}", exc)
        return lens
    if row is None or not row["total"]:
        return lens
    total = float(row["total"])
    contrib = float(row["contributions"] or 0)
    program = float(row["program"] or 0)
    other = max(total - contrib - program, 0.0)
    nodes = [FlowNode(name="Nonprofit sector")]
    links: List[FlowLink] = []
    for label, val in (("Contributions & grants", contrib), ("Program service revenue", program), ("Other revenue", other)):
        if val <= 0:
            continue
        nodes.append(FlowNode(name=label))
        pct = round(100.0 * val / total) if total else 0
        links.append(FlowLink(
            source=0, target=len(nodes) - 1, value=val, value_label=money_fmt(val),
            meta=FlowMeta(title=label, subtitle=f"~{pct}% of sector revenue",
                          url="/nonprofits", source_label="990 aggregate"),
        ))
    if not links:
        return lens
    lens.nodes, lens.links, lens.placeholder = nodes, links, False
    lens.head_amount = money_fmt(total)
    # mdm_organization_nonprofit has no usable state column, so this lens is
    # always the U.S. sector — label it as such rather than imply it's local.
    lens.head_label = "U.S. nonprofit sector revenue"
    lens.count_label = f"{int(row['orgs']):,} orgs · 990 · nationwide"
    return lens


@router.get("", response_model=MoneyFlowResponse)
async def get_money_flow(
    state: Optional[str] = Query(None, description="2-letter or full state name"),
    city: Optional[str] = Query(None, description="City name"),
) -> MoneyFlowResponse:
    state_code = normalize_state_input(state)
    if state_code and city:
        scope_label = f"{city}, {state_code}"
    elif city:
        scope_label = city
    elif state_code:
        scope_label = state_code
    else:
        scope_label = "Local government"
    location_label = scope_label if (state_code or city) else "the U.S."

    with tracer.start_as_current_span("money-flow") as span:
        span.set_attribute("money_flow.state", state_code or "")
        span.set_attribute("money_flow.city", city or "")
        pool = await get_db_pool()

        # Run the three lenses concurrently, each on its own pooled connection
        # (asyncpg cannot multiplex queries on a single connection). Each builder
        # is internally defensive (failure -> placeholder, never raises), so the
        # gather always resolves. Wall-clock collapses from the serial sum of the
        # three queries to the slowest single one.
        async def _with_conn(builder):
            async with pool.acquire() as conn:
                return await builder(conn)

        spending, grants, economy = await asyncio.gather(
            _with_conn(lambda c: _spending(c, state_code=state_code, city=city, scope_label=scope_label)),
            _with_conn(lambda c: _grants(c, state_code=state_code)),
            _with_conn(_economy),
        )

    return MoneyFlowResponse(
        location_label=location_label,
        lenses={"spending": spending, "grants": grants, "economy": economy},
    )
