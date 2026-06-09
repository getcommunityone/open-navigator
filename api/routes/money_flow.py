"""
"Follow the money" flow endpoint — GET /api/money-flow.

Returns Sankey-flow data for three lenses, ALL traced to the warehouse (no
fabricated numbers, per CLAUDE.md):
  - spending : real money-flagged decisions (public.item_interestingness,
               net_dollar_impact), jurisdiction -> decision.
  - grants   : real 990 Schedule I grant flows (public.grant), grantor -> grantee.
  - economy  : the largest nonprofits in scope by total 990 revenue
               (scope -> org), with the headline showing the real scope-wide
               sector total — NOT invented funder->grantee edges.

WIRE-FORMAT: every displayed number is a STRING (head_amount / value_label). The
link `value` stays NUMERIC because the Sankey layout needs it to size links — it
is a chart magnitude, not a bare number rendered to the user.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

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
    # Per-node drill-down target. Set on BOTH source and target nodes so either
    # side of the Sankey is clickable (a grantor node drills to that grantor's
    # grants just as a grantee node drills to the grantee's). None = not clickable.
    url: Optional[str] = None


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
    # Aggregate drill-down for the headline figure (e.g. the full decisions /
    # grants / nonprofit list behind the summed total). None = not clickable.
    head_url: Optional[str] = None
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
           votes_yes, votes_no, total_votes, jurisdiction_id
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
    # Source node drill-down: when every spending row sits in a SINGLE jurisdiction
    # (i.e. a city-scoped view like "Tuscaloosa, AL"), drill into that jurisdiction's
    # own page rather than the broad geocoded decisions map. Multi-jurisdiction scopes
    # (state-only or the U.S.) fall back to the decisions map for this scope; each
    # decision node still drills to that decision's detail page.
    juris_ids = {r["jurisdiction_id"] for r in rows if r["jurisdiction_id"]}
    if len(juris_ids) == 1:
        src_url = f"/jurisdiction/{quote(str(next(iter(juris_ids))))}/meetings"
    elif state_code:
        src_url = f"/decisions-map?state={quote(state_code)}"
    else:
        src_url = "/decisions-map"
    nodes = [FlowNode(name=_trunc(src, 24), url=src_url)]
    links: List[FlowLink] = []
    total = 0.0
    for r in rows:
        amt = abs(float(r["net_dollar_impact"]))
        total += amt
        nodes.append(FlowNode(
            name=_trunc(r["title"] or "Untitled decision", 40),
            url=f"/decisions/{r['event_decision_id']}",
        ))
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
    # Drill down to the full geocoded decisions map, scoped to this state when known.
    lens.head_url = f"/decisions-map?state={quote(state_code)}" if state_code else "/decisions-map"
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
            # Every org node (grantor or grantee) drills to its own grants search.
            node_url = f"/search?q={quote(key)}&types=grants" if key else "/search?types=grants"
            nodes.append(FlowNode(name=_trunc(key, 28), url=node_url))
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
        # Drill down to this specific grantee's grants (not a generic grants list).
        grantee = (r["grantee_name"] or "").strip()
        url = f"/search?q={quote(grantee)}&types=grants" if grantee else "/search?types=grants"
        links.append(FlowLink(
            source=s, target=t, value=amt, value_label=money_fmt(amt),
            meta=FlowMeta(title=r["grantee_name"], subtitle=sub or None,
                          url=url, source_label="990 Schedule I"),
        ))
    lens.nodes, lens.links, lens.placeholder = nodes, links, False
    lens.head_amount = money_fmt(total)
    lens.head_label = "in grant flows"
    # Drill down to the full grants list (990 Schedule I flows).
    lens.head_url = "/search?types=grants"
    lens.count_label = f"{len(links)} grants · 990 Schedule I"
    return lens


# Pre-aggregated nonprofit-sector revenue by scope, 1 row per scope_key — built by
# the `nonprofit_sector_revenue` mart so this lens is a PK lookup, NOT a 3.6M-row
# scan of mdm_organization_nonprofit (which has no geo of its own). The mart joins
# the satellite to its master org for state_code/city_norm. scope_key is one of
# 'us' | 'state:AL' | 'city:AL|tuscaloosa' (city_norm lowercased). We fetch the
# candidate keys most-specific-first and use the first non-empty grain (city ->
# state -> us), so a city with no 990 orgs still shows honest state/national
# context instead of an empty lens.
_ECONOMY_SQL = """
    SELECT scope_key, scope, state_code, city_norm,
           COALESCE(contributions, 0)           AS contributions,
           COALESCE(program_service_revenue, 0) AS program,
           COALESCE(total_revenue, 0)           AS total,
           COALESCE(org_count, 0)               AS orgs
    FROM nonprofit_sector_revenue
    WHERE scope_key = ANY($1::text[])
"""

# Top nonprofits in scope, by total 990 revenue — these are the Sankey links (the
# "top items"). We show the largest orgs rather than a contributions/program/other
# split because the gt990_* component columns are too sparsely populated for that
# decomposition to be meaningful (it collapses to ~all "Other revenue"). The grain
# filter mirrors whichever scope the headline mart row matched, so orgs and total
# line up. city_norm is the lowercased master value, matched exactly.
_ECONOMY_TOP_SQL = """
    SELECT o.org_name,
           COALESCE(n.gt990_total_revenue, n.revenue) AS revenue,
           n.ntee_description
    FROM mdm_organization_nonprofit n
    JOIN mdm_organization o USING (master_org_id)
    WHERE COALESCE(n.gt990_total_revenue, n.revenue) > 0
      AND ($1::text IS NULL OR o.state_code = $1)
      AND ($2::text IS NULL OR o.city_norm = $2)
    ORDER BY COALESCE(n.gt990_total_revenue, n.revenue) DESC
    LIMIT 6
"""


def _economy_scope_keys(state_code: Optional[str], city: Optional[str]) -> List[str]:
    """Candidate scope_keys, most-specific first: city -> state -> us."""
    keys: List[str] = []
    if state_code and city:
        keys.append(f"city:{state_code}|{city.strip().lower()}")
    if state_code:
        keys.append(f"state:{state_code}")
    keys.append("us")
    return keys


async def _economy(conn, *, state_code: Optional[str], city: Optional[str], scope_label: str) -> FlowLens:
    lens = FlowLens(accent=_ACCENT["economy"])
    candidates = _economy_scope_keys(state_code, city)
    try:
        rows = await conn.fetch(_ECONOMY_SQL, candidates)
    except Exception as exc:  # noqa: BLE001
        logger.warning("money-flow economy failed: {}", exc)
        return lens
    by_key = {r["scope_key"]: r for r in rows}
    # First candidate (most specific) with a real, non-zero total.
    row = next((by_key[k] for k in candidates if k in by_key and by_key[k]["total"]), None)
    if row is None:
        return lens
    total = float(row["total"])
    matched_scope = row["scope"]
    # Match the org list to the grain the headline matched (NULL = no filter at
    # that level). city_norm from the mart is already lowercased.
    g_state = row["state_code"]
    g_city = row["city_norm"]
    try:
        top = await conn.fetch(_ECONOMY_TOP_SQL, g_state, g_city)
    except Exception as exc:  # noqa: BLE001
        logger.warning("money-flow economy top-orgs failed: {}", exc)
        return lens
    if not top:
        return lens

    # Source node + headline labels by the grain that actually matched (which may
    # differ from what was requested if a city fell back to its state/national
    # context), so the figure never implies a scope it doesn't have.
    if matched_scope == "city":
        src_name = scope_label
        src_url = f"/search?types=organizations&state={quote(g_state)}&city={quote(g_city)}"
        lens.head_label = f"{scope_label} nonprofit revenue"
        lens.count_label = f"{int(row['orgs']):,} nonprofits · 990"
    elif matched_scope == "state":
        src_name = g_state
        src_url = f"/search?types=organizations&state={quote(g_state)}"
        lens.head_label = f"{g_state} nonprofit revenue"
        lens.count_label = f"{int(row['orgs']):,} nonprofits · 990"
    else:  # 'us'
        src_name = "U.S. nonprofits"
        src_url = "/nonprofits"
        lens.head_label = "U.S. nonprofit sector revenue"
        lens.count_label = f"{int(row['orgs']):,} nonprofits · 990 · nationwide"

    nodes = [FlowNode(name=_trunc(src_name, 24), url=src_url)]
    links: List[FlowLink] = []
    for r in top:
        name = (r["org_name"] or "Unnamed nonprofit").strip()
        rev = float(r["revenue"])
        # Each org node drills to its own organization search.
        org_url = f"/search?q={quote(name)}&types=organizations" if name else "/nonprofits"
        nodes.append(FlowNode(name=_trunc(name, 40), url=org_url))
        links.append(FlowLink(
            source=0, target=len(nodes) - 1, value=rev, value_label=money_fmt(rev),
            meta=FlowMeta(title=name, subtitle=(r["ntee_description"] or None),
                          url=org_url, source_label="IRS 990"),
        ))
    lens.nodes, lens.links, lens.placeholder = nodes, links, False
    # Headline stays the real scope-wide total (all orgs in scope), not just the
    # top few shown as links.
    lens.head_amount = money_fmt(total)
    lens.head_url = src_url
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
        async with pool.acquire() as conn:
            spending = await _spending(conn, state_code=state_code, city=city, scope_label=scope_label)
            grants = await _grants(conn, state_code=state_code)
            economy = await _economy(conn, state_code=state_code, city=city, scope_label=scope_label)

    return MoneyFlowResponse(
        location_label=location_label,
        lenses={"spending": spending, "grants": grants, "economy": economy},
    )
